"""Focused physical and API regression checks for the prescription adapter."""

import copy
import json
from pathlib import Path

import numpy as np
import pytest

from prescription import (
    PRIMARY_UM,
    WAVELENGTHS_UM,
    build_optic,
    catalog_material,
    prescription_facts,
    spherical_sag,
    validate_prescription,
)


def _doublet():
    return json.loads((Path(__file__).resolve().parents[1] / "examples" / "doublet.json").read_text())


def test_spherical_sag_has_signed_curvature_and_plane_limit():
    expected = 20.0 - np.sqrt(20.0**2 - 8.0**2)
    assert spherical_sag(20.0, 8.0) == pytest.approx(expected, abs=1e-14)
    assert spherical_sag(-20.0, 8.0) == pytest.approx(-expected, abs=1e-14)
    assert spherical_sag(None, 100.0) == 0.0
    with pytest.raises(ValueError):
        spherical_sag(20.0, 20.0)


def test_cemented_doublet_counts_two_elements_and_one_sensor_clearance():
    spec = _doublet()
    assert validate_prescription(spec) == []
    facts = prescription_facts(spec)
    assert facts["element_count"] == 2
    assert facts["sensor_distance_from_last_interface_mm"] == pytest.approx(spec["surfaces"][-1]["thickness_after_mm"])
    assert min(e["edge_thickness_mm"] for e in facts["elements"]) >= 1.0


def test_unequal_face_apertures_cannot_hide_a_thin_glass_edge():
    spec = {"stop_surface": 0, "stop_radius_mm": 1.0, "surfaces": [
        {"radius_mm": 20.0, "thickness_after_mm": 3.0, "material_after": {"catalog": "SCHOTT", "name": "N-BK7"}, "clear_radius_mm": 2.0},
        {"radius_mm": -20.0, "thickness_after_mm": 30.0, "material_after": "AIR", "clear_radius_mm": 8.0},
    ]}
    errors = validate_prescription(spec)
    assert any("edge thickness" in x for x in errors)


def test_air_gap_surface_overlap_is_rejected():
    spec = {"stop_surface": 0, "stop_radius_mm": 2.0, "surfaces": [
        {"radius_mm": None, "thickness_after_mm": 3.0, "material_after": {"catalog": "SCHOTT", "name": "N-BK7"}, "clear_radius_mm": 8.0},
        {"radius_mm": 20.0, "thickness_after_mm": 1.0, "material_after": "AIR", "clear_radius_mm": 8.0},
        {"radius_mm": -20.0, "thickness_after_mm": 3.0, "material_after": {"catalog": "SCHOTT", "name": "F2"}, "clear_radius_mm": 8.0},
        {"radius_mm": None, "thickness_after_mm": 50.0, "material_after": "AIR", "clear_radius_mm": 8.0},
    ]}
    assert any("caps intersect" in x for x in validate_prescription(spec))


def test_small_stop_cannot_hide_overlap_of_nonadjacent_glass_blanks():
    spec = {"stop_surface": 2, "stop_radius_mm": 0.5, "surfaces": [
        {"radius_mm": None, "thickness_after_mm": 3.0, "material_after": {"catalog": "SCHOTT", "name": "N-BK7"}, "clear_radius_mm": 8.0},
        {"radius_mm": 20.0, "thickness_after_mm": 0.5, "material_after": "AIR", "clear_radius_mm": 8.0},
        {"radius_mm": None, "thickness_after_mm": 0.5, "material_after": "AIR", "clear_radius_mm": 1.0},
        {"radius_mm": -20.0, "thickness_after_mm": 3.0, "material_after": {"catalog": "SCHOTT", "name": "F2"}, "clear_radius_mm": 8.0},
        {"radius_mm": None, "thickness_after_mm": 50.0, "material_after": "AIR", "clear_radius_mm": 8.0},
    ]}
    errors = validate_prescription(spec)
    # Each air interval clears the tiny stop, but the large lens blanks overlap.
    assert not any("Air interval" in x for x in errors)
    assert any("Nonadjacent surfaces 1 and 3" in x for x in errors)
    # Opening the physical space fixes the overlap without changing the stop.
    spec["surfaces"][1]["thickness_after_mm"] = 2.0
    spec["surfaces"][2]["thickness_after_mm"] = 2.0
    assert validate_prescription(spec) == []


def test_unknown_state_and_invalid_caps_cannot_enter_canonical_optic():
    spec = _doublet()
    spec["apodization"] = "custom"
    assert validate_prescription(spec)
    spec = _doublet()
    spec["surfaces"][0]["radius_mm"] = 4.0
    assert any("mechanical radius" in x for x in validate_prescription(spec))
    spec = _doublet()
    spec["stop_radius_mm"] = 100.0
    assert any("stop radius" in x for x in validate_prescription(spec))


def test_canonical_optic_keeps_one_stop_and_full_requested_ray_bundle():
    spec = _doublet()
    original = copy.deepcopy(spec)
    lens = build_optic(spec, [0.0, 1.5, 3.0])
    assert spec == original
    assert lens.apodization is None
    assert all(f.vx == f.vy == 0 for f in lens.fields.fields)
    assert lens.primary_wavelength == PRIMARY_UM
    assert [w.value for w in lens.wavelengths] == list(WAVELENGTHS_UM)
    assert sum(s.is_stop for s in lens.surfaces.surfaces) == 1
    px = np.array([0.0, 0.5, -0.5, 0.0])
    py = np.array([0.0, 0.0, 0.0, 0.5])
    rays = lens.ray_tracer.trace_generic(0.0, 1.0, px, py, PRIMARY_UM)
    assert len(rays.x) == len(px)
    assert np.all(np.isfinite(rays.x)) and np.all(np.isfinite(rays.y))
    assert np.all(rays.i > 0)
    report = lens.ray_tracer.ray_generator.aimer.last_report
    assert report.converged and report.num_converged == len(px)
    assert report.final_residual <= 1e-9
    stop = lens.surfaces[spec["stop_surface"] + 1]
    assert np.max(np.hypot(stop.x - px * spec["stop_radius_mm"], stop.y - py * spec["stop_radius_mm"])) <= 1e-7


def test_glass_lookup_is_strict_and_traceable_to_a_catalog():
    glass = catalog_material({"catalog": "SCHOTT", "name": "N-BK7"})
    assert glass.material_data["group"] == "glass"
    assert "schott" in glass.material_data["filename"]
    # The enum is important: a raw string crashes to_dict inside robust aiming.
    assert glass.to_dict()["match_policy"] == "strict"
    with pytest.raises(ValueError):
        catalog_material({"catalog": "SCHOTT", "name": "THIS-GLASS-DOES-NOT-EXIST"})
