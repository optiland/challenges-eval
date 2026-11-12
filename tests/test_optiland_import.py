"""Submissions are Optiland lens files; the judge converts and checks them."""

import copy
import json
import math
from pathlib import Path

import pytest

from challenge_evaluator import CHALLENGES, WAVELENGTHS_UM, evaluate_design
from optiland_import import ConversionError, parse_optiland_file, prescription_from_optiland

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = {
    "rms": 6.040034708678789,
    "doublet": 0.18106844456019955,
}


def _load(name):
    return json.loads((ROOT / "examples" / name).read_text(encoding="utf-8"))


def _surface(data, i):
    """Physical surface i (0-based, without the object surface)."""
    return data["surface_group"]["surfaces"][i + 1]


def _stringify_infinity(node):
    """What the website stores: Infinity becomes the string "Infinity"."""
    if isinstance(node, dict):
        return {k: _stringify_infinity(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_stringify_infinity(v) for v in node]
    if isinstance(node, float) and math.isinf(node):
        return "Infinity" if node > 0 else "-Infinity"
    return node


@pytest.mark.parametrize("challenge", ["rms", "doublet"])
@pytest.mark.parametrize("variant", ["optiland", "noapertures.optiland"])
def test_reference_exports_give_the_reference_score(challenge, variant):
    report = evaluate_design(_load(f"{challenge}.{variant}.json"), challenge)
    assert report["status"] == "eligible", report["violations"]
    assert report["input_format"] == "optiland"
    assert report["score"] == pytest.approx(REFERENCE[challenge], rel=1e-12)


def test_infinity_as_string_is_accepted():
    data = _stringify_infinity(_load("doublet.optiland.json"))
    assert '"Infinity"' in json.dumps(data)
    report = evaluate_design(data, "doublet")
    assert report["status"] == "eligible", report["violations"]
    assert report["score"] == pytest.approx(REFERENCE["doublet"], rel=1e-12)


def test_automatic_clear_radius_is_the_real_ray_footprint():
    data = _load("rms.noapertures.optiland.json")
    spec = CHALLENGES["rms"]
    prescription, notes = prescription_from_optiland(data, spec.fields_deg, spec.verification_step_deg, WAVELENGTHS_UM)
    automatic = [n for n in notes if "automatic clear radius" in n]
    assert len(automatic) == len(prescription["surfaces"]) - 1  # every surface except the stop
    stop = prescription["stop_surface"]
    assert prescription["surfaces"][stop]["clear_radius_mm"] == pytest.approx(prescription["stop_radius_mm"])
    # Real rays, not paraxial: surface 1 of this triplet is about 4.6% above
    # the paraxial marginal + chief height (8.264 mm).
    assert prescription["surfaces"][1]["clear_radius_mm"] > 8.264 * 1.04


def test_epd_aperture_gives_the_same_stop_and_score():
    data = _load("doublet.optiland.json")
    data["aperture"] = {"type": "EPD", "value": 12.5}
    report = evaluate_design(data, "doublet")
    assert report["prescription"]["stop_radius_mm"] == pytest.approx(6.25, rel=1e-12)
    assert report["score"] == pytest.approx(REFERENCE["doublet"], rel=1e-12)


def test_image_fno_aperture_is_converted_to_a_stop_radius():
    data = _load("doublet.optiland.json")
    data["aperture"] = {"type": "imageFNO", "value": 8.0}
    spec = CHALLENGES["doublet"]
    prescription, _ = prescription_from_optiland(data, spec.fields_deg, spec.verification_step_deg, WAVELENGTHS_UM)
    assert prescription["stop_radius_mm"] == pytest.approx(6.25, rel=0.02)


def _break(edit):
    data = _load("doublet.optiland.json")
    edit(data)
    return data


@pytest.mark.parametrize(("label", "edit", "message"), [
    ("asphere", lambda d: _surface(d, 0)["geometry"].update(conic=-1.0), "conic"),
    ("tilt", lambda d: _surface(d, 1)["geometry"]["cs"].update(rx=0.01), "tilted"),
    ("decenter", lambda d: _surface(d, 1)["geometry"]["cs"].update(y=0.1), "decentered"),
    ("mirror", lambda d: _surface(d, 2)["interaction_model"].update(is_reflective=True), "mirrors"),
    ("coating", lambda d: _surface(d, 2)["interaction_model"].update(coating={"type": "x"}), "coatings"),
    ("other geometry", lambda d: _surface(d, 0)["geometry"].update(type="EvenAsphere"), "geometry"),
    ("ideal glass", lambda d: _surface(d, 0).update(material_post={"type": "IdealMaterial", "index": 1.5, "absorp": 0.0}), "IdealMaterial"),
    ("abbe glass", lambda d: _surface(d, 0).update(material_post={"type": "AbbeMaterial", "n": 1.5, "abbe": 60}), "not allowed"),
    ("no catalog", lambda d: _surface(d, 0)["material_post"].update(catalog=None, reference=None), "no catalog"),
    ("two stops", lambda d: _surface(d, 1).update(is_stop=True), "exactly one stop"),
    ("no stop", lambda d: _surface(d, 0).update(is_stop=False), "exactly one stop"),
    ("finite object", lambda d: d["surface_group"]["surfaces"][0].update(thickness=1000.0), "infinity"),
    ("curved sensor", lambda d: d["surface_group"]["surfaces"][-1]["geometry"].update(type="StandardGeometry", radius=-100.0), "flat"),
    ("object NA", lambda d: d.update(aperture={"type": "objectNA", "value": 0.1}), "Aperture type"),
    ("annular aperture", lambda d: _surface(d, 2).update(aperture={"type": "RadialAperture", "r_max": 8.0, "r_min": 1.0}), "annular"),
    ("polygon aperture", lambda d: _surface(d, 2).update(aperture={"type": "PolygonAperture"}), "RadialAperture"),
    ("not optiland", lambda d: d.pop("surface_group"), "not an Optiland lens file"),
])
def test_files_outside_the_rules_are_rejected(label, edit, message):
    data = _break(edit)
    with pytest.raises(ConversionError, match=message):
        if "surface_group" not in data:
            parse_optiland_file(data)
        else:
            spec = CHALLENGES["doublet"]
            prescription_from_optiland(data, spec.fields_deg, spec.verification_step_deg, WAVELENGTHS_UM)


def test_rejection_is_reported_as_invalid_prescription():
    data = _break(lambda d: _surface(d, 0)["geometry"].update(conic=-1.0))
    report = evaluate_design(data, "doublet")
    assert report["status"] == "invalid_prescription"
    assert report["score"] is None
    assert any("conic" in v for v in report["violations"])


def test_judge_settings_in_the_file_are_ignored():
    data = _load("doublet.optiland.json")
    tampered = copy.deepcopy(data)
    for field in tampered["fields"]["fields"]:
        field["vy"] = 0.5  # vignetting factors must not change the result
    tampered["wavelengths"]["wavelengths"] = tampered["wavelengths"]["wavelengths"][:1]
    report = evaluate_design(tampered, "doublet")
    assert report["score"] == pytest.approx(REFERENCE["doublet"], rel=1e-12)
    assert any("Ignored from the file: fields" in n for n in report["conversion_notes"])
