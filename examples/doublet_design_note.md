# Doublet validation fixture

`doublet.json` is a regression example for the proposed version 2 achromatic-doublet rules. It demonstrates an attainable legal starting point. It is not an optimized competition submission.

## Provenance and construction

The starting form is Optiland's `CementedAchromat` sample, which cites Milton Laikin, *Lens Design*, fourth edition, page 45. The sample was read at Optiland commit `61f096bbf038b29a19681aabda5a061bf839b40c`:

https://github.com/optiland/optiland/blob/61f096bbf038b29a19681aabda5a061bf839b40c/optiland/samples/simple.py

The sample radii were scaled by five. The crown and flint center thicknesses were then set to 3.0 mm and 2.1 mm, respectively, to provide practical thickness margins at an 8 mm clear radius. A two-variable paraxial root solve adjusted the first two radii to give a 100 mm d-line EFL and equal F- and C-line rear focal positions. The third radius remained fixed. The solve took 11 function evaluations; there was no image-quality or global optimization. The sensor was placed at the paraxial d-line rear focal plane.

The materials are the exact SCHOTT catalog records N-BAK1 and SF2. Wavelengths are 0.4861327, 0.5875618 and 0.6562725 micrometres, with the d line primary. The stop is at the first surface, with a 6.25 mm radius. Every physical lens surface has an 8 mm clear radius.

## Verified optical and mechanical values

| Quantity | Value |
|---|---:|
| d-line EFL | 100.0000000 mm |
| Entrance pupil diameter | 12.5000000 mm |
| Nominal f-number | 8.0000000 |
| Sensor distance from last vertex | 97.27089449 mm |
| Total track | 102.37089449 mm |
| Crown center / edge thickness | 3.0000 / 1.613922 mm |
| Flint center / edge thickness | 2.1000 / 2.828375 mm |
| F-line paraxial rear focal distance | 97.31515926 mm |
| C-line paraxial rear focal distance | 97.31515926 mm |
| Absolute axial F–C separation | Less than 0.000001 mm numerically |
| Crown Abbe number / isolated power | 57.54931 / +0.02430948 per mm |
| Flint Abbe number / isolated power | 33.84824 / −0.01448535 per mm |

The doublet rules have no total-track maximum; the 80 mm limit belongs to the other two challenges. The close F/C agreement is a nominal paraxial property, not a manufacturing tolerance or a claim that all wavelengths share one focus. The d-line focus is about 0.0443 mm ahead of the common F/C focus.

## Independent real-ray check

The prescription passed `validate_prescription`. It was rebuilt with `build_optic` and traced using robust ray aiming. The check used 12 Gaussian quadrature rings in squared pupil radius and 32 azimuthal arms, plus 32 near-rim rays at normalized radius `1 - 1e-7`, at each wavelength and each field in 0°, 0.5°, 1°, 1.5°, 2°, 2.5°, 3°.

All test rays reached the sensor with finite coordinates and positive intensity. This is a sampled check, not a proof about every point in the continuous pupil. Final acceptance should use the common evaluator's prescribed sampling, numerical tolerance, and convergence checks.

Polychromatic RMS radii use one common wavelength-combined centroid per field and equal wavelength weights. Distortion is computed from the d-line chief ray relative to `100 mm × tan(field angle)`.

| Semi-field | Polychromatic RMS radius | Distortion |
|---|---:|---:|
| 0° | 3.671814 micrometres | 0% by definition |
| 1.5° | 2.339965 micrometres | −0.00115775% |
| 3° | 14.082773 micrometres | −0.00463573% |

These values give an estimated version 2 RMS score of 0.18106844 for equal field weights and a 20 micrometre normalization. The finalized common evaluator remains authoritative. The nonzero outer-field blur is intentional: the fixture tests valid evaluation and is not presented as the best possible design.
