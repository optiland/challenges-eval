"""Write the reference designs as Optiland lens files (save_optiland_file).

For each example two files are written:

* ``<name>.optiland.json``: every surface has a physical aperture equal to the
  clear radius of the canonical example. It must give the reference score.
* ``<name>.noapertures.optiland.json``: no physical apertures. The judge
  calculates automatic clear radii from the real-ray footprint.

The glass ``filename`` entries contain the path of the local Optiland
installation; they are replaced by the path inside the package. The judge
ignores them.

Run from the repository root:  python examples/make_optiland_exports.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from challenge_evaluator import CHALLENGES  # noqa: E402
from optiland.fileio import save_optiland_file  # noqa: E402
from prescription import build_optic  # noqa: E402


def _relative_glass_paths(node):
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "filename" and isinstance(value, str) and "/database/" in value.replace("\\", "/"):
                tail = value.replace("\\", "/").rsplit("/database/", 1)[-1]
                node[key] = "optiland/database/" + tail
            else:
                _relative_glass_paths(value)
    elif isinstance(node, list):
        for item in node:
            _relative_glass_paths(item)


def export(name: str) -> None:
    canonical = json.loads((ROOT / "examples" / f"{name}.json").read_text(encoding="utf-8"))
    optic = build_optic(canonical, CHALLENGES[name].fields_deg)
    for suffix, keep_apertures in ((".optiland.json", True), (".noapertures.optiland.json", False)):
        if not keep_apertures:
            for i, surface in enumerate(optic.surfaces.surfaces[1:-1]):
                if i != canonical["stop_surface"]:
                    surface.aperture = None
        path = ROOT / "examples" / f"{name}{suffix}"
        save_optiland_file(optic, str(path))
        data = json.loads(path.read_text(encoding="utf-8"))
        _relative_glass_paths(data)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print("wrote", path.relative_to(ROOT))


if __name__ == "__main__":
    for challenge in ("rms", "doublet", "wide_angle"):
        export(challenge)
