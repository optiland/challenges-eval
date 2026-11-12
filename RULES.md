# Challenge rules: version 2.0.0

These rules define the evaluator in this repository. The competition owner
approved them on 12 November 2026. Scores of an earlier rules version keep
their earlier meaning and are not mixed with version 2 scores.

## 1. Common optical model

1. Design one centered, rotationally symmetric, sequential refractive system
   for an object at infinity.
2. Use only plane or spherical interfaces, homogeneous isotropic catalog
   glass, and air. A plane is the infinite-radius case. Aspheres, mirrors,
   diffractive or phase surfaces, GRIN, coordinate breaks, decentered surfaces,
   custom material functions and curved sensors are outside these challenges.
3. Use exactly one circular aperture stop. It may coincide with a physical
   interface or be represented by one plane in an air space. Its vertex must
   lie between the first and last refracting vertices, inclusive. A stop at a
   glass or cemented interface is permitted in this nominal model.
4. All fields and wavelengths must form their image on one submitted flat
   sensor plane, perpendicular to the axis. Its position is a design variable.
   The judge does not refocus any individual field or wavelength.
5. Lengths are in millimetres and field angles in degrees. The wavelength
   values are exactly 0.4861327, 0.5875618 and 0.6562725 micrometres, with the
   middle wavelength primary. Each wavelength has weight 1/3.
6. Use the pinned catalog records at their packaged reference conditions.
   Specify both catalog and material name. Fuzzy substitutions and custom
   optical constants are not permitted. The judge uses the real refractive
   indices supplied by those records. AIR is modeled as n=1, k=0. No thermal
   or pressure correction is applied.
7. The model is unpolarized and has no user-supplied coatings or apodization.
   Catalog absorption remains in the scalar diffraction pupil amplitudes.
   The geometric RMS measure is separately defined in Section 4.

## 2. Mechanical geometry

1. Declare each physical surface's clear radius. The judge uses that fixed
   circular aperture; it does not enlarge apertures after tracing.
2. Declare the stop radius separately. It must be no larger than the clear
   radius of the surface carrying the stop. The stop may be smaller than the
   glass blank on which it lies.
3. An element is one non-air interval between physical interfaces. A
   cemented doublet has two elements and one shared internal interface.
   A zero-thickness fictitious glass interval is not an element. Adjacent
   identical-material interfaces are rejected; the sole allowed same-medium
   dummy interface is the plane AIR-to-AIR stop.
4. The mechanical radius of an air-spaced element is the larger of its two
   face clear radii. A contiguous cemented group has the largest clear radius
   of all its faces as its common mechanical radius. This defines the
   cylindrical-blank geometry used for edge thickness and overlap checks.
5. Every glass interval must have at least 2 mm center thickness and 1 mm
   edge thickness at its mechanical radius.
6. A spherical cap must be real over its mechanical radius, with
   `mechanical_radius < abs(radius_of_curvature)`.
7. Use the vertex-connected cap. For signed R and radial coordinate r, its
   sag is `s(R,r) = r^2 / (R * (1 + sqrt(1 - r^2/R^2)))`; plane sag is zero.
   For two interfaces with axial spacing t, their separation is
   `g(r) = t + s_back(r) - s_front(r)`.
8. Physical caps must not cross over their shared mechanical radius. The
   judge checks all physical cap pairs, including large surfaces separated
   by a smaller stop. For this centered spherical/plane cap model, checking
   axis and edge gives the minimum separation. Numerical comparisons allow
   1e-9 mm; this is not a manufacturing tolerance.
9. Air spacings may be zero if the surfaces do not cross. Cemented contacts
   are represented by a single shared interface rather than duplicate
   zero-gap spherical interfaces. Mount clearances, bevels and glue-layer
   thickness are outside the nominal benchmark.
10. BFD is the axial distance from the last refracting vertex to the submitted
    sensor. Total track is the axial distance from the first refracting
    vertex to that sensor. Neither quantity is an effective focal length.

## 3. Vignetting and ray validation

**Mechanical vignetting is not permitted.** The full prescribed pupil must
pass the fixed clear apertures for the stated verification fields and
wavelengths. Natural off-axis illumination falloff is allowed; no relative-
illumination or total-transmission requirement is implied by this rule.

The judge reconstructs all field vignetting factors as zero. It fixes the
actual stop diameter with Optiland's `float_by_stop_size` aperture and uses
robust real-ray aiming with at most 50 iterations and a 1e-9 mm solver
tolerance. Paraxial entrance-pupil diameter is then measured, not used to
resize the submitted physical stop.

The geometric pupil sample is a full disk: 16 Gauss-Legendre rings in squared
normalized stop radius and 64 equally spaced azimuths, for 1,024 weighted
samples. The weights sum to one. Verification adds a chief ray and 256 equally
spaced rim rays at normalized radius 0.999999. Rim and chief rays verify the
bundle; they are not additional nonzero-weight RMS samples.

Verification fields are:

| Challenge | Verification semi-field angles |
|---|---|
| RMS | 0 through 14 degrees in 1-degree steps |
| Doublet | 0 through 3 degrees in 0.25-degree steps |
| Wide angle | 0 through 30 degrees in 1-degree steps |

Every combination is traced at all three wavelengths. At every physical
interface and at the sensor, required samples must have finite coordinates
and direction cosines and positive intensity. A missing, blocked, totally
internally reflected or failed ray cannot be removed to improve the score.

The judge also checks forward travel along each ray (allowance 1e-8 mm), the
vertex-connected spherical cap (residual at most 1e-7 mm), and the requested
stop intersection (residual at most 1e-7 mm). Ray aiming must report convergence.

The denser RMS quadrature and the actual scalar-FFT pupil nodes must also pass
the ray checks. The latter are checked immediately after their full-pupil
traces, before subsequent reference-ray traces overwrite the snapshots.

These finite grids define reproducible acceptance checks. They do not prove
continuous clearance for every unsampled ray and field. The numerical
tolerances above are calculation tolerances, not fabrication tolerances.

## 4. Common image-quality definitions

### Polychromatic RMS spot radius

For field i, wavelength k and pupil sample j, let r_ikj be the two-dimensional
sensor intersection. Let q_j be the normalized pupil-area weight. Define

```
c_i   = (1/3) sum_k sum_j q_j r_ikj
R_i^2 = (1/3) sum_k sum_j q_j ||r_ikj - c_i||^2
```

R_i is a radius in millimetres. A single combined centroid is used at each
field. Independently centering each colour is not permitted, since that would
remove lateral colour from the blur measure. This is a geometric stop-area
measure; ray intensity is used for validity, not to suppress aberrated rays
through a user-chosen weighting.

Scoring fields have equal weights that sum to one. Verification fields do not
receive extra score weight merely because there are more of them.

### Distortion

Use the real d-line chief ray aimed through the physical stop center. For
nonzero field angle theta,

```
D(theta) = y_chief,d(theta) / (f_d * tan(theta)) - 1
```

The implementation converts degrees to radians for tan. D is a fraction:
0.02 means 2%. Define D(0)=0 by convention. Apply limits to abs(D), so both
barrel and pincushion distortion count. Check the limit at every verification
field. The ideal mapping is tied to d-line EFL, not to a separately fitted
plate scale at the submitted sensor.

### First-order quantities and axial colour

Compute EFL at 0.5875618 micrometres. Nominal f-number is positive EFL divided
by the absolute paraxial entrance-pupil diameter. Check the submitted physical
stop against this definition.

For each colour, trace a collimated paraxial axial ray and obtain its focus
offset from the common sensor as `-y/u`. The difference between the F and C
focus positions is the primary axial-colour measure. It is not the difference
between their effective focal lengths.

### Polychromatic diffraction MTF

Use Optiland's scalar pupil FFT with a 256-point grid across the pupil diameter
and an explicitly padded 1024-by-1024 FFT. Keep the submitted image plane and
use the chief-ray reference with `remove_tilt=False`.

Compute a complex OTF for each wavelength and each direction. Register all
colours in the same physical sensor coordinates, retaining their chief-ray
image shifts and the sign of the pupil-to-image mapping. Interpolate complex
OTF components at 20 cycles/mm on each direction's physical frequency axis.
Then combine the complex OTFs with equal detected-energy weights and take
the magnitude. Do not average monochromatic MTF magnitudes.

Tangential means image-y spatial modulation for these y-meridional fields;
sagittal means image-x modulation. The score includes both directions.
Catalog absorption affects the monochromatic pupil amplitudes; each OTF is
normalized by its own detected energy. This is a three-wavelength nominal
contrast benchmark, not a spectral throughput or sensor-response model.

## 5. Challenge-specific requirements and scores

| Requirement | RMS | Doublet | Wide angle |
|---|---|---|---|
| EFL | 50 mm +/-1% | 100 mm +/-1% | 24 mm +/-2% |
| Nominal f-number | 4 +/-2% | 8 +/-2% | 4 +/-5% |
| Glass elements | 3-6 | Exactly 2 | 5-8 |
| BFD | At least 10 mm | At least 60 mm | At least 12 mm |
| Total track | At most 80 mm | No added limit | At most 80 mm |
| Absolute distortion | At most 2% | At most 0.5% | At most 2% |
| Scoring semi-fields | 0, 7, 10, 12, 14 degrees | 0, 1.5, 3 degrees | 0, 10, 20, 30 degrees |
| Other conditions | Common rules | EPD 12.5 mm; axial F-C <=0.10 mm | Covers full 60-degree field |

The EPD equality for the doublet uses a numerical allowance of 1e-6 mm. Given
the EFL range, it already implies an f-number range of 7.92 to 8.08, inside the
stated f/8 +/-2% range. It is intentionally retained and documented as a
redundant first-order check.

For the doublet, either element order and either cemented or air-spaced form
are allowed. The glass with the larger Abbe number must form a positive
isolated thick element in air, and the lower-Abbe glass a negative one. The
two Abbe numbers must differ. Use the exact stated F/d/C wavelengths and
the isolated thick-lens power

```
V_d = (n_d - 1) / (n_F - n_C)
Phi = (n_d - 1) * (1/R1 - 1/R2 + (n_d - 1)*t/(n_d*R1*R2))
```

Plane curvatures are zero. This gives an operational crown/flint definition
that can be checked without relying on a material name's spelling.

For eligible designs, the scores are exactly:

```
RMS:        M = mean_i((R_i / 0.025 mm)^2)
Doublet:    M = mean_i((R_i / 0.020 mm)^2)
Wide angle: M = mean_over_fields_and_two_directions((1 - MTF_i,direction(20 lp/mm))^2)
```

Lower is better. No penalty P is added to an eligible score. A constraint
failure yields no ranked score. Entrants may still use any penalty function
they find useful inside their own optimizer.

## 6. Numerical verification and result status

The reference engine is Optiland commit
`61f096bbf038b29a19681aabda5a061bf839b40c` with the catalog packaged at that
commit. `engine_lock.json` records and verifies a SHA-256 digest over the
engine Python files and catalog data. The required numerical dependencies are
pinned in the supplied requirements. NumPy CPU floating-point evaluation is
used; entrant GPU/optimizer precision does not change the judging backend.

Re-evaluate geometric RMS on 32 radial rings by 128 azimuths. At each scoring
field the change must be no more than the larger of 1e-8 mm and 0.1% of the
denser RMS. Keep the declared 16-by-64 score if this check passes.

For MTF, repeat with a 512-point pupil diameter and 2048-by-2048 FFT. Every
field/direction must change by at most 0.005 absolute MTF. Keep the declared
256-by-1024 score if this check passes. This is a sampling-consistency gate,
not an independent validation of the scalar pupil-FFT approximation.

The report contains `eligible`, `official`, `status`, `score`, `violations`,
constraint values and limits, per-field metrics, ray counts, convergence
results and engine provenance. `status` is exactly one of:

| Status | Meaning |
|---|---|
| `eligible` | All checks pass. |
| `invalid_prescription` | The file is not a valid prescription: schema, glass name, spherical cap, crossing surfaces or stop position. |
| `constraint_failed` | A challenge requirement fails: EFL, f-number, element count, BFD, track, thickness, distortion, EPD, axial colour or glass pair. |
| `ray_validation_failed` | A required ray is blocked, lost, totally internally reflected or mis-aimed. |
| `needs_numerical_review` | All requirements pass, but a convergence gate fails. A maintainer reviews the design. |
| `evaluator_error` | The evaluator failed. |

`official` is true only in the locked environment (engine digest, NumPy and
SciPy versions). Outside it, the evaluator still calculates every metric and
lists the differences in `environment_warnings`. Only an `eligible` and
`official` result has a ranked `score`. An eligible result outside the
locked environment has `unofficial_score` instead. `diagnostic_optical_score`,
when present for a design that is not eligible, must never be treated as a
leaderboard score.

## 7. Publication and review

Publish the rules, source, environment lock and all three reference results
together. The judge's numeric prescription is authoritative; an accompanying
notebook may explain the optimization but cannot replace the judge.

Use only one evaluator version on a leaderboard. Publish per-field results
and constraint margins with each score, so a single scalar does not conceal
weak edge performance. Before prize decisions, inspect and independently
cross-check leading prescriptions, and use the same denser verification for
close contenders. The package implements per-design evaluation, not the
hosting or prize-adjudication process.
