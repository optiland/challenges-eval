# Doublet reference design

`doublet.json` is a valid starting point for the doublet challenge, not an
optimized entry.

## Construction

Start: Optiland's `CementedAchromat` sample (Laikin, *Lens Design*, 4th ed.,
p. 45) at commit `61f096bb`.

1. All radii scaled by 5.
2. Crown and flint center thicknesses set to 3.0 mm and 2.1 mm, for margin at
   an 8 mm clear radius.
3. A paraxial root solve on the first two radii (11 evaluations) for 100 mm
   d-line EFL and equal F and C rear focus. The third radius stays fixed.
4. Sensor at the d-line paraxial focus.

Glasses: SCHOTT N-BAK1 and SF2. Stop on the first surface, radius 6.25 mm.
Every lens surface has an 8 mm clear radius.

## Values

| Quantity | Value |
|---|---:|
| d-line EFL | 100.0000000 mm |
| Entrance pupil diameter | 12.5000000 mm |
| f-number | 8.0000000 |
| BFD | 97.27089449 mm |
| Total track | 102.37089449 mm |
| Crown center / edge thickness | 3.0000 / 1.613922 mm |
| Flint center / edge thickness | 2.1000 / 2.828375 mm |
| F and C paraxial rear focus | 97.31515926 mm (both) |
| Axial F–C separation | below 1e-6 mm |
| Crown Abbe number / power | 57.54931 / +0.02430948 per mm |
| Flint Abbe number / power | 33.84824 / −0.01448535 per mm |

The d-line focus is about 0.0443 mm in front of the common F/C focus.

| Semi-field | Polychromatic RMS radius | Distortion |
|---|---:|---:|
| 0° | 3.671814 µm | 0% |
| 1.5° | 2.339965 µm | −0.00115775% |
| 3° | 14.082773 µm | −0.00463573% |

Score: 0.18106844456019955. The full report is
[`../validation/doublet_evaluation.json`](../validation/doublet_evaluation.json).
