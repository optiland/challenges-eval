"""Polychromatic scalar-FFT MTF for the Optiland challenges.

This is part of the challenge evaluator, not an Optiland API. It is
written and tested against commit 61f096bbf038b29a19681aabda5a061bf839b40c.
It retains complex monochromatic OTFs, restores relative chief-ray image
displacements, combines wavelengths, and only then takes the magnitude.

The caller must first validate the prescription and all required ray bundles.
The supported competition model is a centered, rotationally symmetric,
unpolarized system with a common flat image plane, meridional fields, and no
vignetting or user-defined coatings/apodization. Catalog absorption is retained
in the pupil amplitude; spectral weights describe detected energy. This wrapper
does not certify prescription eligibility.
It inherits Optiland's scalar pupil-FFT approximation, including approximately
affine pupil-to-image-direction mapping. It is not a full diffraction integral
or an independent validation of Optiland's optical model.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import numpy as np

OPTILAND_COMMIT = "61f096bbf038b29a19681aabda5a061bf839b40c"


def combine_otfs(
    otfs: np.ndarray,
    image_shifts_mm: np.ndarray,
    wavelength_weights: Sequence[float],
    frequency_lpmm: float,
) -> np.ndarray:
    """Combine spectral OTFs in one physical image coordinate system.

    Args:
        otfs: Complex array shaped (wavelength, field, orientation).
        image_shifts_mm: Same shape; PSF-reference displacements in millimetres.
        wavelength_weights: Nonnegative detected-energy weights, one per wavelength.
        frequency_lpmm: Common image-space frequency in cycles/mm.

    Returns:
        Complex polychromatic OTF with shape (field, orientation). Orientation
        0 is tangential (image y); orientation 1 is sagittal (image x).

    Raises:
        ValueError: If dimensions, frequency, weights, or data are invalid.
    """
    values = np.asarray(otfs, dtype=np.complex128)
    shifts = np.asarray(image_shifts_mm, dtype=np.float64)
    weights = np.asarray(wavelength_weights, dtype=np.float64)
    if values.ndim != 3 or shifts.shape != values.shape:
        raise ValueError("OTFs and shifts must share shape (wavelength, field, axis).")
    if weights.shape != (values.shape[0],):
        raise ValueError("One spectral weight is required per wavelength.")
    if not np.isfinite(frequency_lpmm) or frequency_lpmm < 0:
        raise ValueError("Spatial frequency must be finite and nonnegative.")
    if not np.all(np.isfinite(values)) or not np.all(np.isfinite(shifts)):
        raise ValueError("OTF data and image shifts must be finite.")
    if not np.all(np.isfinite(weights)) or np.any(weights < 0) or weights.sum() <= 0:
        raise ValueError("Spectral weights must be finite, nonnegative, and nonzero.")
    weights = weights / weights.sum()
    # Fourier convention: OTF(f) = integral PSF(x) exp(-2 pi i f x) dx.
    registration = np.exp(-2j * np.pi * frequency_lpmm * shifts)
    return np.sum(weights[:, None, None] * values * registration, axis=0)


def _chief_image_xy(optic, field: tuple[float, float], wavelength: float) -> np.ndarray:
    rays = optic.trace_generic(*field, 0.0, 0.0, wavelength)
    if not np.all(np.isfinite(np.asarray(rays.i))) or not np.all(np.asarray(rays.i) > 0):
        raise ValueError("The chief ray is lost or has invalid intensity.")
    optic.image_surface.geometry.cs.localize(rays)
    xy = np.array([np.asarray(rays.x).item(), np.asarray(rays.y).item()], dtype=float)
    if not np.all(np.isfinite(xy)):
        raise ValueError("The chief ray has nonfinite image coordinates.")
    return xy


def _complex_slices(psf: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    image = np.asarray(psf, dtype=np.float64)
    if image.ndim != 2 or image.shape[0] != image.shape[1] or image.shape[0] % 2:
        raise ValueError("An even square PSF array is required.")
    if not np.all(np.isfinite(image)) or np.any(image < 0) or image.sum() <= 0:
        raise ValueError("PSF must have finite nonnegative values and positive energy.")
    # ifftshift removes the array-centre translation before phase is used.
    otf = np.fft.fft2(np.fft.ifftshift(image))
    otf /= otf[0, 0]
    half = image.shape[0] // 2
    return otf[:half, 0], otf[0, :half]


def _physical_axis_orientation(optic, field, wavelength) -> np.ndarray:
    # In the diffraction integral, the image displacement couples to the
    # outgoing ray direction. FFT's negative exponential therefore makes a
    # positive array coordinate a positive physical image coordinate only if
    # that outgoing direction decreases with the normalized pupil coordinate.
    # A pupil inversion reverses this sign, while the built-in MTF frequency
    # scales deliberately retain only unsigned bandwidths.
    p = 1.0 - 1e-7  # Interior probes avoid roundoff at the aperture boundary.
    rays = optic.trace_generic(
        *field,
        np.array([0.0, 0.0, p, -p]),
        np.array([p, -p, 0.0, 0.0]),
        wavelength,
    )
    optic.image_surface.geometry.cs.localize(rays)
    if not np.all(np.isfinite(np.asarray(rays.i))) or not np.all(np.asarray(rays.i) > 0):
        raise ValueError("A marginal direction probe is lost.")
    directions = np.column_stack((np.asarray(rays.L), np.asarray(rays.M)))
    if not np.all(np.isfinite(directions)):
        raise ValueError("Nonfinite marginal directions prevent OTF registration.")
    tangential = directions[0] - directions[1]
    sagittal = directions[2] - directions[3]
    if abs(tangential[0]) > 1e-9 or abs(sagittal[1]) > 1e-9:
        raise ValueError("The FFT pupil axes are coupled; the meridional evaluator is unsupported.")
    slopes = np.array([tangential[1], sagittal[0]])
    if np.any(abs(slopes) < 1e-12):
        raise ValueError("A degenerate pupil direction prevents OTF registration.")
    return -np.sign(slopes)


def _interpolate_otf(frequencies: np.ndarray, values: np.ndarray, target: float) -> complex:
    axis = np.asarray(frequencies, dtype=np.float64)
    if axis.shape != values.shape or not np.all(np.isfinite(axis)):
        raise ValueError("Invalid monochromatic spatial-frequency axis.")
    if axis[0] != 0 or np.any(np.diff(axis) <= 0):
        raise ValueError("Spatial-frequency axis must start at zero and increase.")
    if target > axis[-1]:
        raise ValueError("Requested frequency is outside the sampled OTF range.")
    # Interpolate real and imaginary components, never the magnitudes alone.
    return complex(np.interp(target, axis, values))


def polychromatic_fft_mtf(
    optic,
    fields: Sequence[tuple[float, float]],
    wavelengths: Sequence[float] = (0.4861327, 0.5875618, 0.6562725),
    wavelength_weights: Sequence[float] = (1.0, 1.0, 1.0),
    frequency_lpmm: float = 20.0,
    pupil_samples: int = 256,
    fft_size: int = 1024,
    snapshot_validator: Callable[[Any, np.ndarray, np.ndarray], None] | None = None,
) -> dict:
    """Evaluate both MTF orientations without moving the submitted image plane.

    Args:
        optic: Already-validated Optiland Optic in the competition model.
        fields: Normalized meridional fields, e.g. (0, angle/max_angle).
        wavelengths: Exact vacuum wavelengths in micrometres.
        wavelength_weights: Detected-energy weights, normalized internally.
        frequency_lpmm: Frequency in cycles per millimetre on the image plane.
        pupil_samples: Grid points across each pupil diameter, explicitly set.
        fft_size: Even FFT size, at least twice pupil_samples to avoid circular
            autocorrelation overlap. Zero padding does not increase pupil density.
        snapshot_validator: Optional read-only callback (optic, Px, Py). It runs
            immediately after each ScalarFFTPSF has traced its exact uniform
            pupil, before any further chief or frequency-axis trace. The
            callback can validate all recorded surface hits, forward travel,
            physical cap intersections and stop-aim residuals, and must raise
            ValueError if any condition fails. It must not trace new rays.

    Returns:
        JSON-serializable metrics and diagnostics. No focus, tilt-removal,
        wavelength recentering, or per-field best-focus operation is performed.

    Raises:
        ValueError: For unsupported settings or nonfinite optical results.
        RuntimeError: If the active Optiland backend is not NumPy.
    """
    import optiland.backend as be
    from optiland.mtf.fft import ScalarFFTMTF
    from optiland.psf.fft import ScalarFFTPSF

    if be.get_backend() != "numpy":
        raise RuntimeError("The reference evaluator requires the NumPy backend.")
    if optic.polarization_state is not None:
        raise ValueError("The competition evaluator requires unpolarized optics.")
    coords = [tuple(float(v) for v in field) for field in fields]
    if not coords or any(len(field) != 2 for field in coords):
        raise ValueError("At least one two-coordinate field is required.")
    if not all(np.isfinite(field).all() and field[0] == 0.0 for field in coords):
        raise ValueError("This evaluator requires finite meridional fields (Hx=0).")
    wls = np.asarray(wavelengths, dtype=np.float64)
    weights = np.asarray(wavelength_weights, dtype=np.float64)
    if wls.ndim != 1 or not len(wls) or not np.all(np.isfinite(wls)) or np.any(wls <= 0):
        raise ValueError("Wavelengths must be a nonempty positive finite sequence.")
    if weights.shape != wls.shape or np.any(weights < 0) or not np.all(np.isfinite(weights)):
        raise ValueError("Nonnegative finite weights must match the wavelengths.")
    if weights.sum() <= 0:
        raise ValueError("At least one spectral weight must be positive.")
    weights = weights / weights.sum()
    if not isinstance(pupil_samples, int) or pupil_samples < 32:
        raise ValueError("pupil_samples must be an integer of at least 32.")
    if not isinstance(fft_size, int) or fft_size % 2 or fft_size < 2 * pupil_samples:
        raise ValueError("fft_size must be even and at least twice pupil_samples.")
    if not np.isfinite(frequency_lpmm) or frequency_lpmm < 0:
        raise ValueError("Spatial frequency must be finite and nonnegative.")

    class CompletePupilFFTMTF(ScalarFFTMTF):
        """Reject missing samples on the exact FFT pupil before using its PSF."""

        def _calculate_psf(self):
            self.psf = []
            axis = np.linspace(-1.0, 1.0, self.num_rays)
            xx, yy = np.meshgrid(axis, axis)
            expected_count = int(np.count_nonzero(xx * xx + yy * yy <= 1.0))
            for field in self.resolved_fields:
                psf_model = ScalarFFTPSF(
                    self.optic,
                    field,
                    self.resolved_wavelength,
                    self.num_rays,
                    self.grid_size,
                    "chief_ray",
                    False,
                )
                data = psf_model.get_data(field, self.resolved_wavelength)
                intensity = np.asarray(data.intensity, dtype=float)
                if intensity.shape != (expected_count,):
                    raise ValueError("The FFT pupil has an unexpected sample count.")
                valid = np.isfinite(intensity) & (intensity > 0)
                for name in ("opd", "pupil_x", "pupil_y", "pupil_z"):
                    values = np.asarray(getattr(data, name), dtype=float)
                    valid &= np.isfinite(values)
                if not np.all(valid):
                    lost = int(np.count_nonzero(~valid))
                    raise ValueError(
                        f"The FFT pupil loses {lost} of {expected_count} rays at "
                        f"field {field}, wavelength {self.resolved_wavelength} um."
                    )
                aiming = getattr(self.optic.ray_tracer.ray_generator.aimer, "last_report", None)
                if aiming is not None and not aiming.converged:
                    raise ValueError("Ray aiming did not converge on the exact FFT pupil grid.")
                if snapshot_validator is not None:
                    px = np.asarray(psf_model.distribution.x, dtype=float)
                    py = np.asarray(psf_model.distribution.y, dtype=float)
                    if px.shape != (expected_count,) or py.shape != (expected_count,):
                        raise ValueError("The recorded FFT pupil has an unexpected shape.")
                    try:
                        snapshot_validator(self.optic, px, py)
                    except ValueError as exc:
                        raise ValueError(
                            f"FFT grid validation failed at field {field}, "
                            f"wavelength {self.resolved_wavelength} um: {exc}"
                        ) from exc
                self.psf.append(psf_model.psf)

    primary = float(optic.primary_wavelength)
    reference_xy = np.array([_chief_image_xy(optic, field, primary) for field in coords])
    mono_otfs = np.empty((len(wls), len(coords), 2), dtype=np.complex128)
    shifts = np.empty(mono_otfs.shape, dtype=np.float64)
    per_wavelength = []
    for k, wavelength in enumerate(wls):
        chief_xy = np.array([_chief_image_xy(optic, field, float(wavelength)) for field in coords])
        shifts[k] = (chief_xy - reference_xy)[:, [1, 0]]  # T=y, S=x.
        orientations = np.array([
            _physical_axis_orientation(optic, field, float(wavelength))
            for field in coords
        ])
        model = CompletePupilFFTMTF(
            optic,
            fields=coords,
            wavelength=float(wavelength),
            num_rays=pupil_samples,
            grid_size=fft_size,
            max_freq=frequency_lpmm,
            strategy="chief_ray",
            remove_tilt=False,
        )
        for i in range(len(coords)):
            tangential, sagittal = _complex_slices(model.psf[i])
            mono_otfs[k, i, 0] = _interpolate_otf(model.freq_tang[i], tangential, frequency_lpmm)
            mono_otfs[k, i, 1] = _interpolate_otf(model.freq_sag[i], sagittal, frequency_lpmm)
        mono_otfs[k] = np.where(orientations < 0, np.conj(mono_otfs[k]), mono_otfs[k])
        per_wavelength.append({
            "wavelength_um": float(wavelength),
            "weight": float(weights[k]),
            "chief_image_xy_mm": chief_xy.tolist(),
            "chief_shift_tangential_sagittal_mm": shifts[k].tolist(),
            "fft_to_physical_axis_orientation": orientations.tolist(),
            "otf_tangential_real_imag": np.column_stack((mono_otfs[k, :, 0].real, mono_otfs[k, :, 0].imag)).tolist(),
            "otf_sagittal_real_imag": np.column_stack((mono_otfs[k, :, 1].real, mono_otfs[k, :, 1].imag)).tolist(),
        })

    combined = combine_otfs(mono_otfs, shifts, weights, frequency_lpmm)
    mtf = np.abs(combined)
    if np.any(mtf > 1.0 + 1e-10):
        raise ValueError("Computed MTF exceeds unity beyond floating-point tolerance.")
    mtf = np.minimum(mtf, 1.0)
    return {
        "method": "Optiland scalar FFT; complex OTF sum with chief-ray colour registration",
        "expected_optiland_commit": OPTILAND_COMMIT,
        "frequency_lpmm": float(frequency_lpmm),
        "fields_normalized": [list(field) for field in coords],
        "wavelengths_um": wls.tolist(),
        "wavelength_weights": weights.tolist(),
        "pupil_samples": pupil_samples,
        "fft_size": fft_size,
        "reference_wavelength_um": primary,
        "reference_chief_image_xy_mm": reference_xy.tolist(),
        "tangential": mtf[:, 0].tolist(),
        "sagittal": mtf[:, 1].tolist(),
        "per_wavelength": per_wavelength,
    }
