"""Evaluator checks with real Optiland traces."""

import copy
import json
from pathlib import Path

import numpy as np
import pytest

from challenge_evaluator import evaluate_design, polychromatic_rms

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def doublet():
    return json.loads((ROOT / "examples" / "doublet.json").read_text())


@pytest.fixture(scope="module")
def accepted(doublet):
    return evaluate_design(doublet, "doublet")


def test_common_colour_centroid_retains_lateral_colour():
    # Each monochromatic spot is a point, but the combined spot is not.
    xy = np.array([[[-.01, 0]], [[0, 0]], [[.01, 0]]])
    result = polychromatic_rms(xy, np.array([1.0]))
    assert result["rms_mm"] == pytest.approx(np.sqrt(2 / 3) * .01)
    assert result["monochromatic_rms_about_own_centroid_mm"] == [0, 0, 0]


def test_nonfinite_ray_is_rejected_instead_of_omitted():
    with pytest.raises(ValueError, match="nonfinite"):
        polychromatic_rms(np.array([[[np.nan, 0], [0, 0]]]), np.array([.5, .5]))


def test_real_doublet_is_eligible_and_has_reproducible_score(accepted):
    assert accepted["eligible"], accepted["violations"]
    assert accepted["score"] == pytest.approx(.1810684445602, rel=1e-8)
    assert all(row["failed_rays"] == 0 for row in accepted["ray_checks"])
    assert accepted["rms_convergence"]["passed"]
    assert accepted["paraxial"]["axial_FC_mm"] < 1e-6


def test_real_rms_challenge_example_is_eligible():
    prescription = json.loads((ROOT / "examples" / "rms.json").read_text())
    report = evaluate_design(prescription, "rms")
    assert report["eligible"], report["violations"]
    assert report["score"] == pytest.approx(6.040034708678789, rel=1e-8)


def test_clipping_is_ineligible_even_when_some_rays_survive(doublet):
    clipped = copy.deepcopy(doublet)
    clipped["surfaces"][-1]["clear_radius_mm"] = 4.0
    report = evaluate_design(clipped, "doublet")
    assert not report["eligible"]
    assert report["score"] is None
    assert any("Ray validation failed" in message for message in report["violations"])
    assert any(0 < row["valid_rays"] < row["launched_rays"] for row in report["ray_checks"])


def test_submitted_sensor_plane_is_preserved(doublet, accepted):
    defocused = copy.deepcopy(doublet)
    defocused["surfaces"][-1]["thickness_after_mm"] += 1.0
    report = evaluate_design(defocused, "doublet")
    assert report["field_metrics"][0]["rms_mm"] > 5 * accepted["field_metrics"][0]["rms_mm"]
    assert report["paraxial"]["focus_offsets_from_sensor_mm"][1] == pytest.approx(-1.0, abs=1e-8)


def test_submission_cannot_set_its_own_vignetting(doublet):
    modified = copy.deepcopy(doublet)
    modified["field_vignetting"] = .5
    report = evaluate_design(modified, "doublet")
    assert not report["eligible"] and report["score"] is None
    assert any("Top-level keys" in item for item in report["violations"])


def test_invalid_thickness_has_no_ranked_score(doublet):
    thin = copy.deepcopy(doublet)
    thin["surfaces"][0]["thickness_after_mm"] = .1
    report = evaluate_design(thin, "doublet")
    assert report["score"] is None
    assert any("thickness" in item for item in report["violations"])


def test_eligibility_rules_do_not_leak_between_challenges(doublet):
    # This doublet's track exceeds 80 mm. The doublet challenge deliberately
    # has no track limit; applying the RMS rules must reject the same design.
    report = evaluate_design(doublet, "rms")
    assert not report["eligible"] and report["score"] is None
    assert any("element_count" in item for item in report["violations"])
    assert any("total_track_mm" in item for item in report["violations"])
