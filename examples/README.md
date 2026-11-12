# Reference prescriptions

These are feasible regression examples for the proposed v2 rules. They are not
optimized entries or claims about the attainable best score. The complete
reference evaluation reports are in `../validation/`.

## RMS challenge: rms.json

Derived from Optiland's `CookeTriplet` at the pinned commit. To provide a simple
valid example, the glass center thicknesses were changed to 5, 2 and 5 mm, clear
radii to 11, 7 and 9 mm, and all radii multiplied by 1.0097785005714526. A short
one-dimensional paraxial root solve set EFL to 50 mm. The physical stop was set
to give a 12.5 mm paraxial entrance pupil, and the sensor placed at d-line
paraxial focus. No image-quality optimization was performed.

Reference score: 6.040034708678789 (lower is better).

## Doublet: doublet.json

Derived from Optiland's `CementedAchromat`, whose source cites Milton Laikin,
*Lens Design*, 4th edition, page 45. See `doublet_design_note.md` for the exact
construction and independent checks. A short paraxial solve set EFL and F-C
primary axial colour after scaling and increasing glass thicknesses.

Reference score: 0.18106844456019955 (lower is better).

## Wide angle: wide_angle.json

Derived from Optiland's `ReverseTelephoto`. The example was scaled, its glass
thicknesses increased to meet the rules, its front negative lens bent to permit
the required clear aperture, and its EFL restored to 24 mm by a scalar radius
adjustment. Its single sensor was shifted by -0.2 mm from d-line paraxial focus.
This yields a geometry-compliant example with 6 elements, f/4, BFD 24.54395473 mm
and track 66.68649089 mm. No image-quality optimization campaign was run.

Reference score: 0.7033100380293447. The largest absolute MTF change on the
512-pupil/2048-FFT verification grid was 0.0006485828493, below the 0.005 gate.
The full evaluation took 77.4 seconds on the test machine.

## Source attribution

Optiland source is distributed under its MIT license. These numeric examples
derive from the sample prescriptions at:

- https://github.com/optiland/optiland/blob/61f096bbf038b29a19681aabda5a061bf839b40c/optiland/samples/simple.py
- https://github.com/optiland/optiland/blob/61f096bbf038b29a19681aabda5a061bf839b40c/optiland/samples/objectives.py

The original Optiland license is included in `../OPTILAND_LICENSE.txt`.
