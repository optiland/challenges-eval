"""Scientific checks of spectral registration and the Optiland FFT wrapper."""

import unittest

import numpy as np
from optiland.mtf.fft import ScalarFFTMTF
from optiland.samples.objectives import CookeTriplet

from polychromatic_mtf import _complex_slices, combine_otfs, polychromatic_fft_mtf


class SpectralCombinationTests(unittest.TestCase):
    def test_clear_circular_pupil_matches_analytic_incoherent_mtf(self):
        pupil_samples = 512
        axis = np.linspace(-1, 1, pupil_samples)
        x, y = np.meshgrid(axis, axis)
        pupil = ((x*x + y*y) <= 1).astype(float)
        padded = np.pad(pupil, pupil_samples // 2)
        psf = abs(np.fft.fftshift(np.fft.fft2(padded)))**2
        tangent, sagittal = _complex_slices(psf)
        bins = np.array([0, 25, 100, 256, 400])
        normalized_frequency = bins / (pupil_samples - 1)
        expected = 2 / np.pi * (np.arccos(normalized_frequency) - normalized_frequency *
                               np.sqrt(1 - normalized_frequency**2))
        np.testing.assert_allclose(abs(tangent[bins]), expected, atol=5e-4)
        np.testing.assert_allclose(abs(sagittal[bins]), expected, atol=5e-4)

    def test_two_sharp_colours_half_period_apart_cancel(self):
        frequency = 20.0
        otfs = np.ones((2, 1, 2), dtype=complex)
        shifts = np.zeros((2, 1, 2))
        shifts[1, 0, 0] = 1.0 / (2.0 * frequency)
        result = np.abs(combine_otfs(otfs, shifts, [1, 1], frequency))
        np.testing.assert_allclose(result, [[0, 1]], atol=1e-14)

    def test_common_translation_preserves_modulation(self):
        otfs = np.array([[[0.5 + 0.2j, 0.9 + 0.03j]], [[0.7 - 0.1j, 0.8 - 0.04j]]])
        shifts = np.array([[[0.0, 0.0]], [[0.001, -0.003]]])
        before = combine_otfs(otfs, shifts, [2, 1], 20)
        after = combine_otfs(otfs, shifts + np.array([0.113, -0.027]), [2, 1], 20)
        np.testing.assert_allclose(abs(before), abs(after), atol=1e-14)

    def test_complex_combination_does_not_average_magnitudes(self):
        otfs = np.array([[[0.7 + 0.2j, 0.4]], [[-0.7 - 0.2j, 0.8]]])
        result = combine_otfs(otfs, np.zeros((2, 1, 2)), [1, 1], 20)
        np.testing.assert_allclose(result, [[0.0, 0.6]], atol=1e-14)


class OptilandFFTChecks(unittest.TestCase):
    def test_one_colour_matches_builtin_at_a_frequency_bin(self):
        lens = CookeTriplet()
        model = ScalarFFTMTF(lens, fields=[(0, 0.7)], wavelength=0.588,
                             num_rays=128, grid_size=512, remove_tilt=False)
        frequency = float(model.freq_tang[0][8])
        report = polychromatic_fft_mtf(lens, [(0, 0.7)], [0.588], [1],
                                      frequency_lpmm=frequency,
                                      pupil_samples=128, fft_size=512)
        self.assertAlmostEqual(report["tangential"][0], float(model.mtf[0][0][8]), places=12)

    def test_identical_colours_equal_monochromatic_result(self):
        lens = CookeTriplet()
        mono = polychromatic_fft_mtf(lens, [(0, 0.7)], [0.588], [1])
        same = polychromatic_fft_mtf(lens, [(0, 0.7)], [0.588, 0.588], [1, 2])
        np.testing.assert_allclose(same["tangential"], mono["tangential"], atol=1e-14)
        np.testing.assert_allclose(same["sagittal"], mono["sagittal"], atol=1e-14)

    def test_zero_frequency_is_unity_for_all_colours(self):
        report = polychromatic_fft_mtf(CookeTriplet(), [(0, 0), (0, 0.7)], frequency_lpmm=0)
        np.testing.assert_allclose(report["tangential"], [1, 1], atol=1e-14)
        np.testing.assert_allclose(report["sagittal"], [1, 1], atol=1e-14)

    def test_lost_fft_pupil_ray_is_rejected(self):
        from optiland.physical_apertures import EllipticalAperture, RotatedAperture
        lens = CookeTriplet()
        # Chief and four marginal probes survive, but diagonal FFT samples do
        # not. This specifically exercises the complete WavefrontData check.
        lens.surfaces[1].aperture = RotatedAperture(
            EllipticalAperture(a=6.0, b=4.5), angle=np.pi/4,
        )
        with self.assertRaisesRegex(ValueError, "FFT pupil loses"):
            polychromatic_fft_mtf(lens, [(0, 0)], [0.588], [1],
                                  pupil_samples=64, fft_size=256)

    def test_pupil_coordinate_inversion_preserves_complex_image_otfs(self):
        from optiland.distribution import create_distribution

        class InvertedPupil:
            """Reparameterize the identical lens by (Px, Py) -> (-Px, -Py)."""
            def __init__(self, optic):
                self._optic = optic

            def __getattr__(self, name):
                return getattr(self._optic, name)

            def trace_generic(self, Hx, Hy, Px, Py, wavelength, **kwargs):
                return self._optic.trace_generic(Hx, Hy, -Px, -Py, wavelength, **kwargs)

            def trace(self, Hx, Hy, wavelength, num_rays=None, distribution="hexapolar", **kwargs):
                if isinstance(distribution, str):
                    sampling = create_distribution(distribution)
                    sampling.generate_points(num_rays)
                else:
                    sampling = distribution
                return self.trace_generic(Hx, Hy, sampling.x, sampling.y, wavelength, **kwargs)

        lens = CookeTriplet()
        normal = polychromatic_fft_mtf(lens, [(0, 0.7)], pupil_samples=128, fft_size=512)
        inverted = polychromatic_fft_mtf(InvertedPupil(lens), [(0, 0.7)], pupil_samples=128, fft_size=512)
        for key in ("tangential", "sagittal"):
            np.testing.assert_allclose(inverted[key], normal[key], atol=1e-10)
        for original, reflected in zip(normal["per_wavelength"], inverted["per_wavelength"]):
            for key in ("otf_tangential_real_imag", "otf_sagittal_real_imag"):
                np.testing.assert_allclose(reflected[key], original[key], atol=1e-10)
            np.testing.assert_allclose(original["fft_to_physical_axis_orientation"], [[1, 1]])
            np.testing.assert_allclose(reflected["fft_to_physical_axis_orientation"], [[-1, -1]])

    def test_callback_sees_exact_fft_grid_snapshots_before_other_traces(self):
        lens = CookeTriplet()
        counts = []

        def check_snapshots(optic, px, py):
            # A chief or frequency-calibration trace would contain 1 or 5 rays.
            expected = int(np.count_nonzero(
                np.add.outer(np.linspace(-1, 1, 64)**2, np.linspace(-1, 1, 64)**2) <= 1
            ))
            self.assertEqual(len(px), expected)
            self.assertEqual(len(py), expected)
            for surface in optic.surfaces.surfaces[1:]:
                self.assertEqual(np.asarray(surface.x).size, expected)
            counts.append(expected)

        polychromatic_fft_mtf(lens, [(0, 0), (0, .7)], [.588], [1],
                              pupil_samples=64, fft_size=256,
                              snapshot_validator=check_snapshots)
        self.assertEqual(len(counts), 2)

    def test_fft_image_orientation_agrees_with_geometrical_centroid(self):
        # This checks the physical sign used for the chromatic phase registration.
        lens = CookeTriplet()
        field, wavelength = (0, 0.7), 0.588
        nodes, weights = np.polynomial.legendre.leggauss(24)
        radius = np.sqrt((nodes + 1) / 2)
        phi = np.arange(128) * 2 * np.pi / 128
        px = (radius[:, None] * np.cos(phi)).ravel()
        py = (radius[:, None] * np.sin(phi)).ravel()
        area_weights = np.repeat(weights / (2 * 128), 128)
        chief = lens.trace_generic(*field, 0., 0., wavelength)
        chief_y = float(chief.y[0])
        rays = lens.trace_generic(*field, px, py, wavelength)
        geometrical_displacement = np.sum(np.asarray(rays.y) * area_weights) - chief_y
        model = ScalarFFTMTF(lens, fields=[field], wavelength=wavelength,
                             num_rays=256, grid_size=1024, remove_tilt=False)
        psf = np.asarray(model.psf[0])
        pitch = 1 / (psf.shape[0] * float(model.freq_tang[0][1]))
        y = (np.arange(psf.shape[0]) - psf.shape[0] // 2) * pitch
        diffraction_displacement = np.sum(psf.sum(axis=1) * y) / psf.sum()
        # Small pupil-FFT/finite-window differences remain; the displacement is
        # about +1.5 micrometres, so this independently catches a sign reversal.
        self.assertGreater(geometrical_displacement, 0)
        self.assertAlmostEqual(diffraction_displacement, geometrical_displacement, delta=1e-4)


if __name__ == "__main__":
    unittest.main()
