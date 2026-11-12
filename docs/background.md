# Background

Notes on why the rules in [RULES.md](../RULES.md) look the way they do, and
what the evaluator does not model.

## Why one published evaluator

The first version of the challenges stated the optical targets but left open
how a design is judged: vignetting, pupil sampling, how wavelengths are
combined, weights, focus and penalty terms. Rules version 2 fixes all of these
in code that anybody can run. We checked the Optiland behaviour that matters
for judging at commit `61f096bb` [S2–S8]:

- `SpotDiagram` drops rays with zero intensity before it calculates the spot
  radius. A clipped design can therefore look better than it is. The evaluator
  checks every ray first.
- The field factors `vx` and `vy` shrink the pupil. The judge sets them to zero,
  so a lens file cannot change the pupil that is scored.
- `semi_aperture` is a drawing value and does not clip rays. The evaluator uses
  physical `RadialAperture` objects, and it defines the radius used for edge
  thickness.
- `FFTMTF` handles one wavelength. Averaging MTF magnitudes over wavelengths
  loses the chromatic phase, so the evaluator combines complex OTFs instead.
- `Distortion` returns percent and uses its own reference mapping. The rules
  define distortion as a fraction relative to `f_d * tan(theta)`.
- Optimizer constraints are penalties, not pass/fail checks. The judge checks
  each requirement on its own.

## Why mechanical vignetting is not allowed

When the score is spot size, clipping the worst rays lowers the score but
throws away light. Allowing that trade would need a throughput or
relative-illumination limit and more rules on how to sample and weight it.
For starter challenges, we require the full pupil to pass.

Natural illumination falloff off-axis is still allowed. The RMS weights are
equal areas of the stop; they are a convention of this benchmark, not a
radiometric model.

The check uses finite ray grids. It is a reproducible test, not a proof that
no ray anywhere in the pupil is clipped. The rim rays sit one part per million
inside the stop edge to avoid an exact tie with the stop radius.

## Changes to two objectives

**Doublet.** Lateral chromatic aberration alone does not make a lens
achromatic. A thin lens with the stop at the lens has no lateral chromatic
aberration, yet its focus still moves with wavelength [S9]. Version 2 scores
all wavelengths on one sensor and limits the F–C focus separation to 0.10 mm.
That limit is our choice. At f/8 it equals about 6.25 µm of marginal-ray blur
radius (`defocus / (2 * f_number)`).

**Wide angle.** The old score added `D / 0.02`, so 2% distortion cost as much
as the full range of `(1 - MTF)^2`. Version 2 makes 2% a hard limit and ranks
designs by MTF only.

These changes can reorder a leaderboard, so scores from different rules
versions are never mixed.

## What the evaluator does not model

- The geometric trace and the scalar FFT diffraction model are separate. The
  FFT model assumes a near-linear mapping from pupil to image-space ray
  direction. The convergence check tests sampling, not this assumption.
- Each wavelength's OTF is normalized by its own detected energy, and the
  three wavelengths have equal weight. There is no white-light throughput or
  sensor response.
- No coatings, polarization, scattering, tolerances, thermal effects, mounts,
  bevels or manufacturing yield.
- A failed ray aim or convergence check means the rank cannot be certified. It
  does not prove that the design is impossible.

One monochromatic Cooke case matches the OpticStudio value in Optiland's own
tests (see [validation](../validation/VALIDATION.md)). A broadband off-axis
cross-check of a wide-angle design in another program is still open [S10].
For prize decisions, the leading designs get a denser evaluation and a manual
review.

## Sources

- [S1] Challenges page: https://www.optiland.org/competitions
- [S2] Spot diagram: https://github.com/optiland/optiland/blob/61f096bbf038b29a19681aabda5a061bf839b40c/optiland/analysis/spot_diagram/core.py
- [S3] Field vignetting: https://www.optiland.org/docs/api/fields/fields.field_group.html
- [S4] Surface clipping: https://github.com/optiland/optiland/blob/61f096bbf038b29a19681aabda5a061bf839b40c/optiland/surfaces/standard_surface.py
- [S5] MTF base class: https://www.optiland.org/docs/_modules/mtf/base.html
- [S6] Polychromatic PSF in OpticStudio: https://ansyshelp.ansys.com/public/Views/Secured/Zemax/v251/en/OpticStudio_User_Guide/OpticStudio_Help/topics/Huygens_Surface_MTF.html
- [S7] Distortion: https://github.com/optiland/optiland/blob/61f096bbf038b29a19681aabda5a061bf839b40c/optiland/analysis/distortion.py
- [S8] Merit function and constraints: https://www.optiland.org/docs/optimization_merit_constraints.html
- [S9] Chromatic aberration (Edmund Optics): https://www.edmundoptics.com/knowledge-center/application-notes/optics/chromatic-and-monochromatic-optical-aberrations/
- [S10] Cross-tool validation: https://github.com/optiland/optiland/issues/710
