# Reference designs

One valid design per challenge. They show that the requirements can be met
and serve as regression tests. They are not optimized, so their scores are
easy to beat.

| Challenge | File | Based on | Score |
|---|---|---|---:|
| `rms` | `rms.json` | Optiland `CookeTriplet` | 6.040034708678789 |
| `doublet` | `doublet.json` | Optiland `CementedAchromat` (Laikin, *Lens Design*, 4th ed., p. 45) | 0.18106844456019955 |
| `wide_angle` | `wide_angle.json` | Optiland `ReverseTelephoto` | 0.7033100380293447 |

Each design is also stored as an Optiland lens file, the format you submit:

- `<name>.optiland.json` has a physical aperture on every surface;
- `<name>.noapertures.optiland.json` has none, so the judge calculates the
  clear radii.

Both give the score above. `make_optiland_exports.py` writes them from the
`<name>.json` files. The `<name>.json` files use the internal prescription
format of the evaluator. The full reports are in [`../validation/`](../validation/).

## How the designs were made

**RMS.** Glass center thicknesses set to 5, 2 and 5 mm, clear radii to 11, 7
and 9 mm, and all radii scaled by 1.0097785005714526 to give 50 mm EFL. The
stop gives a 12.5 mm entrance pupil, and the sensor is at the d-line paraxial
focus.

**Doublet.** Radii scaled by 5, crown and flint center thicknesses set to 3.0
and 2.1 mm, then the first two radii solved for 100 mm EFL and equal F and C
focus. Details in [doublet_design_note.md](doublet_design_note.md).

**Wide angle.** Scaled, glass made thicker to meet the thickness rules, front
negative lens bent to pass the full aperture, radii scaled back to 24 mm EFL,
and the sensor moved by -0.2 mm along the axis from the d-line paraxial focus.
Six elements, f/4, BFD 24.54395473 mm, track 66.68649089 mm.

No image-quality optimization was run on any of them.

## Source

The designs derive from Optiland samples at commit `61f096bb`
([simple.py](https://github.com/optiland/optiland/blob/61f096bbf038b29a19681aabda5a061bf839b40c/optiland/samples/simple.py),
[objectives.py](https://github.com/optiland/optiland/blob/61f096bbf038b29a19681aabda5a061bf839b40c/optiland/samples/objectives.py)),
used under the Optiland MIT license ([`../OPTILAND_LICENSE.txt`](../OPTILAND_LICENSE.txt)).
