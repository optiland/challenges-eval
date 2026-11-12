# Validation record

Executed 11 November 2026 against Optiland commit
61f096bbf038b29a19681aabda5a061bf839b40c, Python 3.12.14, NumPy 2.5.4 and
SciPy 1.18.1. The 30-package dependency closure is pinned in
`../requirements-lock.txt`. The engine/catalog digest is in
`../engine_lock.json` and in each evaluation report.

## Focused tests

Command run from the package folder:

```bash
python -m pytest -q tests test_prescription.py --junitxml=validation/tests.xml
```

Observed result: **28 passed in 22.18 seconds**. One deprecation warning came
from a preinstalled pytest/anyio plugin, not from the optical calculations.
The machine-readable result is `tests.xml`.

The suite contains 9 evaluator tests, 8 prescription/geometry tests and 11
polychromatic-MTF tests. It exercises real Optiland traces in addition to
analytic invariants. It is intentionally scoped to the evaluator; the full
Optiland upstream suite was not run and no Optiland source was modified.

The numerical tests include lateral-colour variance, a missing ray, a physically
clipped aperture, a moved common sensor plane, invalid glass thickness, and
attempted submission-controlled vignetting. Geometry checks cover signed sag,
cemented element count, strict catalog resolution, unequal face apertures,
and large overlapping lens caps hidden behind a small stop.

MTF checks include a circular pupil's analytic incoherent transfer function,
spectral cancellation, common-translation invariance, complex-OTF versus
magnitude averaging, comparison with Optiland monochromatic MTF, zero
frequency, a diagonal clipping case missed by cardinal rays, correct image
shift sign, inverted pupil coordinates and exact-snapshot callback timing.

## Complete reference evaluations

| Example | Eligible | Score | Largest absolute distortion |
|---|---|---:|---:|
| `rms.json` | Yes | 6.040034708678789 | 0.0027151434% |
| `doublet.json` | Yes | 0.18106844456019955 | 0.0046357277% |
| `wide_angle.json` | Yes | 0.7033100380293447 | 1.6861122633% |

Each example passes the full geometry, first-order, ray and convergence gates
of its own challenge. Their scores are not comparable across challenges.
They establish feasible reference inputs; they are not optimized designs.

### RMS example

Per-field polychromatic RMS radii at 0, 7, 10, 12 and 14 degrees are
39.712663, 30.146848, 45.031279, 68.029306 and 98.657883 micrometres.
The primary verification grid traces 57,645 rays across fields and wavelengths,
with additional rays on the denser score quadrature. All prescribed test rays
pass. See `rms_evaluation.json`.

### Doublet example

Per-field polychromatic RMS radii at 0, 1.5 and 3 degrees are
3.671814, 2.339965 and 14.082773 micrometres. The F-C paraxial axial separation
is below 1e-6 mm. The primary verification grid traces 49,959 rays, plus the
denser score quadrature. See `doublet_evaluation.json`.

### Wide-angle example

The main verification grid traces 119,133 rays. Both scalar-FFT resolutions
also receive the full per-surface ray validation, accounting for 3,072,624
FFT pupil samples across fields, wavelengths and resolutions. Additional rays
check the denser geometric RMS quadrature and chief/marginal references.

The complete evaluation took 77.39 seconds. It returned eligible with no
violations. The maximum absolute change of any tangential/sagittal MTF between
the 256/1024 and 512/2048 calculations was 0.0006485828493, below the prescribed
0.005 threshold. See `wide_angle_evaluation.json`.

The low MTF values in this example are expected: it was adjusted to establish
feasibility and verify the evaluator, without an image-quality optimization.

## Additional MTF evidence and limits

On the unmodified Optiland Cooke sample, with the proposed exact F/d/C
wavelengths, the maximum 256-to-512 pupil refinement change at 20 lp/mm was
0.000413395. The full data is in `mtf_convergence.json`. That sample does not
itself meet all the competition rules.

One separate monochromatic comparison used the independent OpticStudio value
already published in Optiland's cross-tool regression data: full-field
sagittal MTF at 20 lp/mm for its Cooke/Hikari-F2 case. The calculation gave
0.53925255 against the reference 0.53866392, an absolute difference of
0.00058863, within the reference test's 0.002 tolerance. This is evidence for
one case, not universal validation of the broadband wrapper.

The scalar pupil-FFT optical approximation and continuum-wide clearance are
not established by numerical convergence or these finite tests. Before
competition adoption, an independent broadband off-axis comparison is still
advisable. The upstream validation discussion identifies remaining differences:
https://github.com/optiland/optiland/issues/710

## Rerun on Windows, 12 November 2026 (evaluator 2.0.0)

Windows 11, Python 3.12.12, NumPy 2.5.4, SciPy 1.18.1, Optiland installed
with `pip install -r requirements.txt` (Git `core.autocrlf=true`).

- The original digest code reported `environment_mismatch` on this install.
  Cause: `Path` sort order ignores case on Windows, and the catalog `.yml`
  files were checked out with CRLF. The fixed digest gives the locked value
  `5a8a03cf...`.
- Tests: 42 passed (28 original, 4 digest tests, 10 status tests).
- References, evaluated with the CLI:

| Example | Status | Score | Recorded score |
|---|---|---|---|
| `rms.json` | eligible, official | 6.040034708678789 | identical |
| `doublet.json` | eligible, official | 0.18106844456019966 | 0.18106844456019955 (relative 7e-16) |
| `wide_angle.json` | eligible, official | 0.7033100380293447 | identical |

The wide-angle evaluation took about 47 seconds on this machine.
