# Validation record

## Environment

Optiland commit `61f096bbf038b29a19681aabda5a061bf839b40c`, Python 3.12.14 on
Linux, NumPy 2.5.4, SciPy 1.18.1. The full dependency set is pinned in
[`../requirements-lock.txt`](../requirements-lock.txt), and the engine digest is
in [`../engine_lock.json`](../engine_lock.json) and in each report.

## Tests

```bash
python -m pytest -q tests --junitxml=validation/tests.xml
```

The tests run real Optiland traces and check, among others:

- rays: a missing ray, a clipped aperture, vignetting factors in the
  submission, ray aiming;
- geometry: signed sag, cemented element count, strict glass names, unequal
  face apertures, lens caps that overlap behind a small stop;
- scoring: lateral chromatic aberration in the RMS, a moved sensor plane;
- MTF: the analytic MTF of a circular pupil, complex OTF versus magnitude
  averaging, chromatic contrast cancellation, image shift sign, inverted
  pupil coordinates, comparison with Optiland's monochromatic MTF;
- submissions: Optiland lens files, rejected features, the judge.

CI runs the tests on Linux and Windows, and evaluates every reference design.
`tests.xml` is the result of the first run (28 tests, 11 November 2026).

## Reference evaluations

| Design | Status | Score | Largest absolute distortion | Report |
|---|---|---:|---:|---|
| `rms.json` | eligible | 6.040034708678789 | 0.0027151434% | `rms_evaluation.json` |
| `doublet.json` | eligible | 0.18106844456019955 | 0.0046357277% | `doublet_evaluation.json` |
| `wide_angle.json` | eligible | 0.7033100380293447 | 1.6861122633% | `wide_angle_evaluation.json` |

- **RMS:** spot radii at 0, 7, 10, 12, 14° are 39.712663, 30.146848,
  45.031279, 68.029306 and 98.657883 µm. 57,645 verification rays.
- **Doublet:** spot radii at 0, 1.5, 3° are 3.671814, 2.339965 and
  14.082773 µm. Axial F–C separation below 1e-6 mm. 49,959 verification rays.
- **Wide angle:** 119,133 verification rays, plus 3,072,624 MTF pupil samples
  that pass the same ray checks. The largest MTF change between the normal and
  the dense grid is 0.00065 (limit 0.005). The evaluation takes about 77 s.

The MTF values of the wide-angle design are low because nobody optimized it.

## MTF cross-checks

- Optiland Cooke sample at the F, d, C wavelengths: the largest change from
  256 to 512 pupil samples at 20 lp/mm is 0.000413
  ([`mtf_convergence.json`](mtf_convergence.json)).
- Optiland's Cooke/Hikari-F2 case, full-field sagittal MTF at 20 lp/mm:
  0.53925255 against the OpticStudio value 0.53866392 in Optiland's
  regression data. The difference, 0.00059, is inside that test's 0.002
  tolerance. This is one monochromatic case.

A broadband off-axis comparison with another optical program is still open
([optiland#710](https://github.com/optiland/optiland/issues/710)).

## Windows rerun, 12 November 2026 (evaluator 2.0.0)

Windows 11, Python 3.12.12, NumPy 2.5.4, SciPy 1.18.1, Git
`core.autocrlf=true`.

The first digest code gave `environment_mismatch` here: Windows sorts paths
without case, and Git checked out the catalog `.yml` files with CRLF. The
fixed digest gives the locked value `5a8a03cf...`.

| Design | Status | Score |
|---|---|---|
| `rms.json` | eligible, official | 6.040034708678789 (same) |
| `doublet.json` | eligible, official | 0.18106844456019966 (relative difference 7e-16) |
| `wide_angle.json` | eligible, official | 0.7033100380293447 (same) |

The wide-angle evaluation took about 47 s on this machine.
