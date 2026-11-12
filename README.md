# Optiland starter challenges: evaluator v2.1.0

The reference evaluator for the Optiland starter challenges, rules version
2.1.0 (approved 12 November 2026). The same code runs on your computer and in
the official judge. The original proposal was prepared on 11 November 2026;
the history of this repository shows every change since then.

## Recommendation

Use one published, versioned evaluator for eligibility and scoring. Prohibit
mechanical vignetting in these starter challenges, specify one common sensor
plane, define every weighting and reference convention, and publish numeric
reference prescriptions with their evaluation reports.

The recommended objectives are:

| Challenge | Eligible designs are ranked by |
|---|---|
| RMS spot size | Mean squared polychromatic RMS radius / 25 micrometres |
| Achromatic doublet | Mean squared polychromatic RMS radius / 20 micrometres, with an axial F-C separation limit of 0.10 mm |
| Moderate wide angle | Mean squared sagittal and tangential MTF deficits at 20 lp/mm, with an absolute distortion limit of 2% |

See **RULES.md** for the complete specification. Lower scores are better.
Constraint violations never buy a better leaderboard rank: a design that does
not pass all checks has `score: null`.

## What changed, and why

The public page supplies useful optical targets, but leaves choices such as
vignetting, pupil sampling, the detailed polychromatic reduction, weights,
focus and penalty coefficients unclear. The public Optiland code was inspected
at commit `61f096bbf038b29a19681aabda5a061bf839b40c` and exercised locally.

### Findings in the actual code

1. `SpotDiagram` filters out nonpositive-intensity rays before calculating its
   per-wavelength spot radii. It is useful for analysis, but cannot by itself
   establish that a design has passed a no-vignetting rule. The reference judge
   checks every original ray before calculating any score. [S2]
2. Field `vx` and `vy` shrink normalized pupil coordinates by `1-v`. They must
   be zero in a judge-controlled model; otherwise the submitted model can
   change the pupil being evaluated. [S3]
3. A drawing `semi_aperture` is not a physical clipping aperture. The builder
   creates explicit `RadialAperture` objects. The mechanical radius used for
   edge thickness is also explicitly defined. [S4]
4. `FFTMTF` resolves one wavelength. A physical broadband MTF needs an explicit
   combination of complex OTFs or registered intensity PSFs. Averaging the
   monochromatic MTF magnitudes loses chromatic phase information. [S5, S6]
5. `Distortion` returns percent and uses its own plate-scale convention. The
   proposed evaluator instead spells out a fractional `f_d*tan(theta)`
   definition. This avoids both a percent/fraction error and an ambiguous
   reference mapping when the sensor is defocused. [S7]
6. Optiland has paraxial, real-ray, ray-aiming, physical-aperture and scalar
   diffraction capabilities sufficient for this evaluator. It also offers
   optimization constraints, but those are separate from judging a finished
   prescription. Optimizer penalties are not hard eligibility checks. [S8]

These are reasons to make the public contract explicit. They do not establish
that the website's private judge currently makes any particular mistake.

### Why prohibit mechanical vignetting here?

With a spot-size objective, clipping the worst rays can improve the reported
blur at the cost of accepted light. Allowing that tradeoff would require a
defined throughput or relative-illumination constraint, a sampling measure,
and wavelength/field aggregation. For an introductory challenge, requiring the
full prescribed pupil to pass is simpler and scientifically defensible.

This does not require uniform brightness across the image. Natural off-axis
illumination falloff, pupil distortion and catalog absorption are separate from
mechanical clipping. The geometric RMS weights are uniform area in the
normalized physical stop; they are a declared benchmark convention, not a
general radiometric entrance-pupil power integral.

The check is a finite, published verification procedure. It must not be
described as a mathematical proof that no point of a continuous field or pupil
is vignetted. The near-rim samples are deliberately displaced inward by one
part per million to avoid a numerical equality at the physical stop edge.

### Two deliberate objective revisions

**Doublet:** minimizing lateral chromatic aberration alone does not establish longitudinal
achromatism. A thin lens with its stop at the lens can have wavelength-
independent chief-ray height at a fixed sensor while its axial focal position
still changes with wavelength. The new objective evaluates all wavelengths on the
same sensor and explicitly limits the F-C paraxial focus separation. Bringing
F and C to the same longitudinal location is the usual primary achromatic
correction. [S9]

The proposed 0.10 mm bound is a policy choice, not a universal constant. At
f/8, a 0.10 mm paraxial defocus corresponds to roughly 6.25 micrometres of
marginal-ray blur radius, using `radius ~= abs(defocus)/(2*f_number)`. The
reference doublet demonstrates that the proposed constraints are jointly
feasible; its F-C axial separation is below 1e-6 mm.

**Wide angle:** the current `D/0.02` term treats 2% distortion as a cost of one,
equal to the entire range of `(1-MTF)^2`. The new challenge makes 2% a hard
distortion bound and then ranks image contrast within that requirement. This
is a different design objective, not merely a rewording.

### Versioning the change

The no-vignetting rule, exact wavelengths, new doublet score and axial chromatic aberration
bound, hard wide-angle distortion bound, additional verification fields and
shared stop rules can change the ranking. Introduce them as a new challenge
version or new round. Keep old scores attached to their old evaluator. If the
organizers choose to migrate an active round, announce the complete rules and
re-evaluate every eligible submission with the same released code. Do not
silently mix versions on one leaderboard.

## Run the evaluator

Use a separate Python environment. The tests ran with Python 3.12.14 on Linux
and Python 3.12.12 on Windows, on the NumPy CPU backend. In another
environment (for example Colab with other NumPy or SciPy versions) the
evaluator still calculates every metric, but the result is marked
`official: false`. Install the pinned requirements from this folder:

```bash
python -m pip install -r requirements.txt
python -m pytest -q tests test_prescription.py
python challenge_evaluator.py examples/doublet.json --challenge doublet --output result.json
```

`rms`, `doublet` and `wide_angle` select the three specifications. The CLI exits
with code 0 for an eligible result in the locked environment, code 3 for an
eligible result in another environment (`unofficial_score`), and code 2 for
every other status. See RULES.md, section 6, for the status list. It writes a complete JSON report, including constraints, ray failures,
per-field metrics, convergence checks and software provenance.

In a notebook:

```python
import json
from pathlib import Path
from challenge_evaluator import evaluate_design

prescription = json.loads(Path("examples/doublet.json").read_text())
result = evaluate_design(prescription, challenge="doublet")

print(result["status"])
print(result["score"])
for reason in result["violations"]:
    print(reason)
```

This prints an eligible result and a score near `0.1810684445602` for the supplied
doublet. A full wide-angle evaluation was approximately 77 seconds on the test
machine; timings depend on hardware and the prescription. The evaluator does
not run a lens optimization.

## Submission format

Submit an Optiland lens file. In your notebook or script:

```python
from optiland.fileio import save_optiland_file
save_optiland_file(lens, "my_lens.json")
```

Check it locally before you submit:

```bash
python challenge_evaluator.py my_lens.json --challenge rms
```

The judge reads only the optical design: spherical or plane surfaces, their
radii and thicknesses, catalog glasses, the stop and optional physical
apertures (`RadialAperture`). Surfaces without a physical aperture get an
automatic clear radius from the real-ray beam footprint. Fields, wavelengths,
vignetting factors and other analysis settings in the file are ignored; the
judge sets them. Anything outside the challenge model (aspheres, tilts,
mirrors, coatings, model glasses) is rejected with a clear message. See
RULES.md, section 8.

`examples/*.optiland.json` are the three reference designs as Optiland files,
with physical apertures; `examples/*.noapertures.optiland.json` are the same
designs without apertures. All six give the reference scores.

The numeric prescription format of `examples/rms.json`, `doublet.json` and
`wide_angle.json` is the internal format of the evaluator. `evaluate_design`
accepts it too, but submissions use Optiland files.

The judge does not run participant Python. Participants may use any optimizer,
differentiation method, starting form or design software, as long as the final
lens is exported as an Optiland file.

## The official judge

The workflow `.github/workflows/judge.yml` scores the submissions of the
website. It runs when a participant saves a lens file (the website starts it with
`workflow_dispatch`), every 30 minutes, and by hand from the Actions tab.

- The scoring code comes from a release tag (for example `v2.1.0`), never
  from `main`. Each challenge on the website records the evaluator version that
  judges it.
- Each submission runs in its own process with a timeout, on GitHub's Linux
  runners in the locked environment, so its result is official.
- The judge writes a result only if the submission did not change during the
  evaluation. A new submission is judged on the next run.
- The public log shows submission ids, statuses and scores. Prescriptions and
  reports stay private until the deadline of the challenge.

`judge/challenges.json` maps the website challenge slugs to the evaluator
challenge names. To add a challenge: add its specification and reference
design, release a new tag, add the tag to the workflow matrix and the slug to
`judge/challenges.json`.

## What was tested

Three feasible examples were evaluated with all required constraints and
convergence checks. These are regression fixtures, not competitive optimized
designs; their scores are not comparable across different challenges.

| Fixture | Elements | EFL | f-number | Reference score |
|---|---:|---:|---:|---:|
| Modified Cooke triplet | 3 | 50 mm | 4 | 6.040034708679 |
| Modified cemented achromat | 2 | 100 mm | 8 | 0.181068444560 |
| Modified reverse telephoto | 6 | 24 mm | 4 | 0.703310038029 |

The tests also cover clipping rejection, missing rays, wavelength-centroid
separation, preservation of the submitted sensor plane, invalid thickness,
strict material matching, hidden overlap around a small stop, analytical
circular-pupil MTF, chromatic contrast cancellation, the Fourier translation
sign, inverted pupil-coordinate conventions and exact FFT-grid validation.
See `validation/VALIDATION.md` for the executed checks and their results.

## Numerical and physical limits

The geometric trace and the scalar diffraction calculation are distinct
models. The scalar pupil FFT assumes approximately affine mapping from pupil
coordinates to image-space ray directions. Grid refinement tests numerical
sampling error; it does not independently validate that approximation for
every possible prescription. The MTF helper therefore reports its method and
settings explicitly.

Catalog absorption is retained in each monochromatic PSF. Each monochromatic
OTF is normalized by its own detected energy, and the three wavelength weights
are equal detected-energy weights. This is not a white-light throughput or
sensor-response model. Geometric RMS uses its separately stated stop-area
weights. No coatings, polarization, scattering, tolerances, thermal model,
mounts, bevels or manufacturing yield are scored.

An independent OpticStudio comparison already published in Optiland's test
suite was reproduced for one monochromatic Cooke case. Agreement there does
not validate every polychromatic wide-angle design. The upstream cross-tool
validation discussion explicitly lists remaining discrepancies. [S10]

The report distinguishes numerical review from an accepted score. Failed
aiming or insufficient convergence means that no rank can be certified; it
does not by itself prove that the physical design is impossible. The current
package evaluates one prescription and does not implement competition hosting,
untrusted-code execution, submissions, deadlines or prize adjudication.

Before adoption, review the code, freeze the complete environment and catalog,
publish the examples and full evaluation settings, and cross-check at least
one broadband off-axis wide-angle case in an independent optical program.
Close prize-boundary results should undergo a common denser evaluation;
displayed decimal places alone are not evidence of physical accuracy.

## Sources

- [S1] Public challenges, inspected 11 November 2026: https://www.optiland.org/competitions
- [S2] Spot diagram source: https://github.com/optiland/optiland/blob/61f096bbf038b29a19681aabda5a061bf839b40c/optiland/analysis/spot_diagram/core.py
- [S3] Field vignetting: https://www.optiland.org/docs/api/fields/fields.field_group.html
- [S4] Surface tracing and clipping: https://github.com/optiland/optiland/blob/61f096bbf038b29a19681aabda5a061bf839b40c/optiland/surfaces/standard_surface.py
- [S5] Single-wavelength MTF base: https://www.optiland.org/docs/_modules/mtf/base.html
- [S6] Ansys wavelength PSF combination: https://ansyshelp.ansys.com/public/Views/Secured/Zemax/v251/en/OpticStudio_User_Guide/OpticStudio_Help/topics/Huygens_Surface_MTF.html
- [S7] Optiland distortion implementation: https://github.com/optiland/optiland/blob/61f096bbf038b29a19681aabda5a061bf839b40c/optiland/analysis/distortion.py
- [S8] Default merit and constraints: https://www.optiland.org/docs/optimization_merit_constraints.html
- [S9] Edmund Optics on transverse and longitudinal chromatic aberration: https://www.edmundoptics.com/knowledge-center/application-notes/optics/chromatic-and-monochromatic-optical-aberrations/
- [S10] Independent validation discussion: https://github.com/optiland/optiland/issues/710
- [S11] FFT implementation and frequency axes: https://github.com/optiland/optiland/blob/61f096bbf038b29a19681aabda5a061bf839b40c/optiland/mtf/fft.py
- [S12] Chromatic focal shift: https://github.com/optiland/optiland/blob/61f096bbf038b29a19681aabda5a061bf839b40c/optiland/analysis/chromatic_focal_shift.py

Source observations are distinguished above from the proposed competition
policy. The numeric thresholds of the new policy are choices for this
benchmark, not claims of universal optical design limits.
