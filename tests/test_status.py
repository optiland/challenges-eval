"""Each result has exactly one status, and only official eligible results get a score."""

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

import challenge_evaluator
from challenge_evaluator import STATUSES, evaluate_design

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def doublet():
    return json.loads((ROOT / "examples" / "doublet.json").read_text())


def _check_common(report):
    assert report["status"] in STATUSES
    if report["score"] is not None:
        assert report["status"] == "eligible" and report["official"]


def test_eligible_official(doublet):
    report = evaluate_design(doublet, "doublet")
    _check_common(report)
    assert report["status"] == "eligible" and report["official"]
    assert report["score"] is not None and "unofficial_score" not in report


def test_unknown_key_is_invalid_prescription(doublet):
    modified = copy.deepcopy(doublet)
    modified["field_vignetting"] = 0.5
    report = evaluate_design(modified, "doublet")
    _check_common(report)
    assert report["status"] == "invalid_prescription"


def test_unknown_glass_is_invalid_prescription(doublet):
    modified = copy.deepcopy(doublet)
    modified["surfaces"][0]["material_after"] = {"catalog": "SCHOTT", "name": "NOT-A-GLASS"}
    report = evaluate_design(modified, "doublet")
    _check_common(report)
    assert report["status"] == "invalid_prescription", report["violations"]


def test_thin_glass_is_constraint_failed(doublet):
    thin = copy.deepcopy(doublet)
    thin["surfaces"][0]["thickness_after_mm"] = 1.5
    report = evaluate_design(thin, "doublet")
    _check_common(report)
    assert report["status"] == "constraint_failed", report["violations"]
    assert any("minimum_center_thickness_mm" in v for v in report["violations"])


def test_wrong_challenge_rules_are_constraint_failed(doublet):
    report = evaluate_design(doublet, "rms")
    _check_common(report)
    assert report["status"] == "constraint_failed"


def test_clipping_is_ray_validation_failed(doublet):
    clipped = copy.deepcopy(doublet)
    clipped["surfaces"][-1]["clear_radius_mm"] = 4.0
    report = evaluate_design(clipped, "doublet")
    _check_common(report)
    assert report["status"] == "ray_validation_failed"


def test_other_environment_gets_unofficial_score_only(doublet, monkeypatch):
    real = challenge_evaluator.engine_provenance()
    fake = {**real, "mismatch": ["numpy version differs from the published engine lock."]}
    monkeypatch.setattr(challenge_evaluator, "engine_provenance", lambda: fake)
    report = evaluate_design(doublet, "doublet")
    _check_common(report)
    assert report["status"] == "eligible" and not report["official"]
    assert report["score"] is None
    assert report["unofficial_score"] == pytest.approx(0.1810684445602, rel=1e-8)
    assert report["environment_warnings"] == fake["mismatch"]
    assert report["violations"] == []


def test_unexpected_exception_is_evaluator_error(doublet, monkeypatch):
    def broken(*args, **kwargs):
        raise AttributeError("simulated internal failure")

    monkeypatch.setattr(challenge_evaluator, "polychromatic_rms", broken)
    report = evaluate_design(doublet, "doublet")
    _check_common(report)
    assert report["status"] == "evaluator_error" and report["score"] is None
    assert "AttributeError" in report["violations"][-1]


@pytest.mark.parametrize(("name", "edit", "code"), [
    ("ok", None, 0),
    ("clipped", ("clear_radius_mm", 4.0), 2),
])
def test_cli_exit_codes(doublet, tmp_path, name, edit, code):
    prescription = copy.deepcopy(doublet)
    if edit:
        prescription["surfaces"][-1][edit[0]] = edit[1]
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps(prescription))
    result = subprocess.run(
        [sys.executable, str(ROOT / "challenge_evaluator.py"), str(path), "--challenge", "doublet"],
        capture_output=True, text=True, cwd=ROOT, check=False,
    )
    assert result.returncode == code, result.stderr[-2000:]
