# Challenge rules, version 2.1.0

These rules define how the evaluator in this repository judges a design.
Section 1 lists the requirements and the score of each challenge; the other
sections define the terms used there. The reasons behind the rules are in
[docs/background.md](docs/background.md).

## 1. Challenges

| Requirement | RMS (`rms`) | Doublet (`doublet`) | Wide angle (`wide_angle`) |
|---|---|---|---|
| EFL | 50 mm ±1% | 100 mm ±1% | 24 mm ±2% |
| Nominal f-number | 4 ±2% | 8 ±2% | 4 ±5% |
| Glass elements | 3 to 6 | Exactly 2 | 5 to 8 |
| BFD | At least 10 mm | At least 60 mm | At least 12 mm |
| Total track | At most 80 mm | No limit | At most 80 mm |
| Absolute distortion | At most 2% | At most 0.5% | At most 2% |
| Scoring semi-fields | 0, 7, 10, 12, 14° | 0, 1.5, 3° | 0, 10, 20, 30° |
| Verification semi-fields | 0 to 14° in 1° steps | 0 to 3° in 0.25° steps | 0 to 30° in 1° steps |
| Other | | EPD 12.5 mm; axial F–C at most 0.10 mm; crown/flint pair | Full 60° field |

A design that meets every requirement gets a score. Lower is better:

```
RMS:        M = mean_i((R_i / 0.025 mm)^2)
Doublet:    M = mean_i((R_i / 0.020 mm)^2)
Wide angle: M = mean over fields and both directions of (1 - MTF(20 lp/mm))^2
```

R_i is the polychromatic RMS spot radius and MTF the polychromatic diffraction
MTF at scoring field i (section 6). A design that fails any requirement gets
no score. There is no penalty term. You can still use penalties in your own
optimizer.

### Doublet details

- The EPD must be 12.5 mm, with a numerical allowance of 1e-6 mm. Together with
  the EFL range, this already keeps the f-number between 7.92 and 8.08.
- Either element order is allowed, cemented or air-spaced.
- The two glasses must have different Abbe numbers. The glass with the larger
  Abbe number must form the positive element and the other glass the negative
  one, each taken as an isolated thick lens in air:

  ```
  V_d = (n_d - 1) / (n_F - n_C)
  Phi = (n_d - 1) * (1/R1 - 1/R2 + (n_d - 1)*t/(n_d*R1*R2))
  ```

  A plane surface has zero curvature. This test uses the glass data, not the
  glass name.

## 2. Submission

Submit an Optiland lens file written with
`optiland.fileio.save_optiland_file(lens, "my_lens.json")`. The judge reads
only the optical design:

- the object surface, at infinity, and a flat, untilted image surface;
- for each lens surface: spherical (`StandardGeometry` with conic 0) or plane
  geometry, radius, thickness, `is_stop`, the material after the surface, and
  an optional `RadialAperture` with `r_min` = 0;
- the aperture type: `float_by_stop_size`, `EPD` or `imageFNO`.

A material is a catalog glass (`Material` with a name and a catalog or
reference) or air (`IdealMaterial` with index 1 and no absorption). Glass
names must match the pinned catalog exactly.

The judge ignores fields, wavelengths, vignetting factors, ray aiming,
apodization, solves and pickups in the file and lists them in
`conversion_notes`. It rejects tilted or decentered surfaces, aspheres,
mirrors, coatings, scattering models, other materials and other aperture
types as `invalid_prescription`. The report contains the converted
prescription that was judged.

## 3. Optical model

1. One centered, rotationally symmetric, sequential refractive system with the
   object at infinity.
2. Plane or spherical surfaces, catalog glass and air only. Aspheres, mirrors,
   diffractive surfaces, GRIN, coordinate breaks, decentered surfaces, custom
   materials and curved sensors are not allowed.
3. Exactly one circular aperture stop. It can lie on a lens surface (also a
   glass or cemented surface) or on a plane in an air space. It must lie
   between the first and the last lens surface, both included.
4. All fields and wavelengths use one flat sensor plane, perpendicular to the
   axis. You choose its position. The judge does not refocus any field or
   wavelength.
5. Lengths are in mm and field angles in degrees. The wavelengths are
   0.4861327, 0.5875618 (primary) and 0.6562725 µm, each with weight 1/3.
6. Glass data comes from the catalog pinned with Optiland, at its reference
   conditions, with no thermal or pressure correction. Air has n = 1, k = 0.
7. The model is unpolarized, with no coatings or apodization. Catalog
   absorption is kept in the diffraction calculation only.

## 4. Mechanical geometry

1. **Clear radius.** If a surface has a `RadialAperture`, its `r_max` is the
   clear radius, and the judge does not enlarge it. Otherwise the judge sets
   the clear radius to the largest real-ray height on that surface, times
   1.001. It traces the full pupil (32 rings by 128 azimuths, plus 720 rays on
   the rim) at every verification field and wavelength. Paraxial heights are
   not used, because real rays can be more than 25% higher at wide angles.
2. **Stop radius.** `float_by_stop_size` gives the stop diameter directly.
   For `EPD` and `imageFNO`, the judge calculates the stop radius from the
   paraxial marginal ray, then keeps it fixed. The stop can be smaller than
   the lens on which it lies.
3. **Elements.** An element is one glass interval between two surfaces. A
   cemented doublet has two elements that share one surface. A zero-thickness
   glass interval is not an element. Two adjacent surfaces with the same
   medium on both sides are rejected, except a plane stop surface in air.
4. **Mechanical radius.** For an air-spaced element, the larger of its two
   clear radii. For a cemented group, the largest clear radius of all its
   surfaces.
5. **Thickness.** Each glass element needs at least 2 mm center thickness and
   1 mm edge thickness at its mechanical radius.
6. **Real caps.** Each spherical surface needs
   `mechanical_radius < abs(radius_of_curvature)`.
7. **No crossing.** With sag `s(R, r) = r^2 / (R * (1 + sqrt(1 - r^2/R^2)))`
   (zero for a plane), two surfaces with axial spacing t are separated by
   `g(r) = t + s_back(r) - s_front(r)`. This must not be negative at the axis
   or at the smaller mechanical radius of the two. The judge checks all
   surface pairs, also large lenses on both sides of a small stop. The
   numerical allowance is 1e-9 mm.
8. **Air spaces** can be zero if the surfaces do not cross. Model a cemented
   contact as one shared surface, not two surfaces with zero gap. Mounts,
   bevels and glue layers are not modeled.
9. **BFD** is the axial distance from the last lens surface to the sensor.
   **Total track** is the axial distance from the first lens surface to the
   sensor.

## 5. Vignetting and ray checks

**Mechanical vignetting is not allowed.** The full pupil must pass every clear
aperture at every verification field and wavelength. Natural illumination
falloff off-axis is allowed.

The judge sets all field vignetting factors to zero, fixes the stop size with
`float_by_stop_size`, and uses robust ray aiming (at most 50 iterations,
tolerance 1e-9 mm). It then measures the paraxial entrance pupil; it does not
resize the stop.

Pupil sampling: 16 Gauss-Legendre rings in squared normalized stop radius by
64 azimuths, 1,024 samples with weights that sum to one. For the checks only,
the judge adds the chief ray and 256 rim rays at normalized radius 0.999999.

At every surface and at the sensor, each ray must have finite coordinates and
direction cosines and positive intensity. A missing, blocked, totally
internally reflected or failed ray fails the design; it cannot be dropped.
The judge also checks that each ray travels forward (allowance 1e-8 mm), hits
the correct spherical cap (1e-7 mm), and hits the stop where it was aimed
(1e-7 mm). Ray aiming must converge. The denser RMS grid and the pupil
samples of both MTF calculations get the same checks.

These finite grids are reproducible tests, not a proof that no ray anywhere
is clipped. The allowances are numerical, not manufacturing tolerances.

## 6. Definitions

### Polychromatic RMS spot radius

For field i, wavelength k and pupil sample j, let r_ikj be the 2D position on
the sensor and q_j the pupil-area weight:

```
c_i   = (1/3) sum_k sum_j q_j r_ikj
R_i^2 = (1/3) sum_k sum_j q_j ||r_ikj - c_i||^2
```

All wavelengths share one centroid per field, so lateral chromatic aberration
counts in the spot size. Ray intensity is used to check rays, not to weight
them. All scoring fields have equal weight.

### Distortion

From the real d-line chief ray through the stop center, at field angle theta:

```
D(theta) = y_chief,d(theta) / (f_d * tan(theta)) - 1
```

D is a fraction (0.02 = 2%), D(0) = 0, and the limit applies to abs(D) at every
verification field. f_d is the d-line EFL.

### First-order quantities

EFL is calculated at 0.5875618 µm. The nominal f-number is EFL divided by the
paraxial entrance-pupil diameter. The axial F–C separation is the difference
between the paraxial F and C focus positions (`-y/u` of an axial ray, relative
to the sensor). It is not the difference of the focal lengths.

### Polychromatic diffraction MTF

Optiland scalar pupil FFT with 256 samples across the pupil, padded to a
1024 × 1024 FFT, at the submitted sensor, chief-ray reference, `remove_tilt=False`.

For each wavelength and direction, the judge calculates the complex OTF at
20 cycles/mm in sensor coordinates, keeps the image shift of each wavelength,
combines the three OTFs with equal weights and then takes the magnitude.
Averaging MTF magnitudes is not allowed. Tangential is the image-y direction
and sagittal the image-x direction; the score uses both. Each OTF is
normalized by its own detected energy.

## 7. Numerical checks and result status

The engine is Optiland commit `61f096bbf038b29a19681aabda5a061bf839b40c` with
its packaged catalog. `engine_lock.json` holds a SHA-256 digest of the engine
files and catalog data, and `requirements.txt` pins the numerical packages.
The judge calculates on the NumPy CPU backend.

Convergence checks:

- **RMS:** recalculated on 32 rings by 128 azimuths. At each scoring field the
  change must be at most the larger of 1e-8 mm and 0.1%.
- **MTF:** recalculated with 512 pupil samples and a 2048 × 2048 FFT. Each
  value may change by at most 0.005.

If a check passes, the score from the normal grid stands.

The report contains `status`, `official`, `score`, `violations`, all
constraint values and limits, per-field results, ray counts, convergence
results and engine provenance. `status` is one of:

| Status | Meaning |
|---|---|
| `eligible` | All checks pass. |
| `invalid_prescription` | The file is not a valid design: format, glass name, spherical cap, crossing surfaces or stop position. |
| `constraint_failed` | A requirement fails: EFL, f-number, elements, BFD, track, thickness, distortion, EPD, axial F–C or glass pair. |
| `ray_validation_failed` | A required ray is blocked, lost, totally internally reflected or mis-aimed. |
| `needs_numerical_review` | All requirements pass, but a convergence check fails. A maintainer reviews the design. |
| `evaluator_error` | The evaluator failed. |

`official` is true only in the pinned environment (engine digest, NumPy and
SciPy versions). Elsewhere the evaluator still calculates everything, lists
the differences in `environment_warnings`, and gives an `unofficial_score`
instead of `score`. A `diagnostic_optical_score` on a design that is not
eligible is never a leaderboard score.

## 8. Leaderboard

- One leaderboard uses one evaluator version only.
- Per-field results and constraint margins are published with each score.
- Before prizes are given, the leading designs are reviewed, cross-checked
  and evaluated on a denser grid.

## Versions

- **2.1.0** (12 November 2026, before any design was judged): submissions are
  Optiland lens files; surfaces without a physical aperture get an automatic
  real-ray clear radius.
- **2.0.0** (12 November 2026): first version of these rules.

Scores from different rules versions are never mixed.
