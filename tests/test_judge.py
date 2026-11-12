"""The judge writes exactly one result per pending submission, and only if the
row did not change during the evaluation."""

import datetime as dt
import json
import urllib.parse
from pathlib import Path

import pytest

from judge.run_pending import judge_pending, main, result_columns, run_evaluator

ROOT = Path(__file__).resolve().parents[1]
NOW = dt.datetime(2026, 11, 12, 12, 0, tzinfo=dt.timezone.utc)
SLUGS = {"rms-slug": "rms", "doublet-slug": "doublet"}


class FakeSupabase:
    """In-memory tables with the PostgREST filters the judge uses."""

    def __init__(self):
        self.competitions = [
            {"id": "c-rms", "slug": "rms-slug", "evaluator_version": "2.1.0"},
            {"id": "c-dbl", "slug": "doublet-slug", "evaluator_version": "2.1.0"},
            {"id": "c-old", "slug": "rms-slug", "evaluator_version": "2.0.0"},
            {"id": "c-new", "slug": "unknown-slug", "evaluator_version": "2.1.0"},
        ]
        self.submissions = {}
        self.designs = {}

    def add(self, sub_id, comp, prescription="P", minutes_old=60, status="pending"):
        t = (NOW - dt.timedelta(minutes=minutes_old)).isoformat()
        self.submissions[sub_id] = {"id": sub_id, "competition_id": comp, "status": status,
                                    "created_at": t, "updated_at": t, "score": None}
        if prescription is not None:
            self.designs[sub_id] = {"submission_id": sub_id, "prescription": prescription,
                                    "updated_at": t, "report": None}

    @staticmethod
    def _filters(query):
        out = {}
        for part in query.split("&"):
            key, _, value = part.partition("=")
            out[key] = urllib.parse.unquote(value)
        return out

    def select(self, table, query):
        f = self._filters(query)
        if table == "competitions":
            version = f["evaluator_version"].removeprefix("eq.")
            return [{"id": c["id"], "slug": c["slug"]} for c in self.competitions if c["evaluator_version"] == version]
        assert table == "competition_submissions"
        ids = f["competition_id"].removeprefix("in.(").removesuffix(")").split(",")
        rows = [s for s in self.submissions.values() if s["status"] == "pending" and s["competition_id"] in ids]
        rows.sort(key=lambda s: s["created_at"])
        out = []
        for s in rows[: int(f["limit"])]:
            d = self.designs.get(s["id"])
            embed = {"prescription": d["prescription"], "updated_at": d["updated_at"]} if d else None
            out.append({**{k: s[k] for k in ("id", "competition_id", "created_at", "updated_at")},
                        "competition_submission_designs": embed})
        return out

    def update(self, table, query, body):
        f = self._filters(query)
        if table == "competition_submission_designs":
            d = self.designs.get(f["submission_id"].removeprefix("eq."))
            if d and d["updated_at"] == f["updated_at"].removeprefix("eq."):
                d.update(body)
                return [d]
            return []
        s = self.submissions.get(f["id"].removeprefix("eq."))
        if s and s["status"] == "pending" and s["updated_at"] == f["updated_at"].removeprefix("eq."):
            s.update(body)
            return [s]
        return []


def report(status="eligible", official=True, score=1.25, violations=()):
    return {"status": status, "official": official, "score": score if status == "eligible" and official else None,
            "violations": list(violations)}


def run(db, evaluate, logs=None):
    return judge_pending(db, "2.1.0", SLUGS, evaluate, now=NOW, log=(logs.append if logs is not None else lambda _: None))


def test_eligible_official_result_is_written():
    db = FakeSupabase()
    db.add("s1", "c-rms")
    seen = []
    results = run(db, lambda p, c: seen.append((p, c)) or report())
    assert seen == [("P", "rms")]
    s = db.submissions["s1"]
    assert (s["status"], s["official"], s["score"], s["is_valid"], s["evaluator_version"]) == ("eligible", True, 1.25, True, "2.1.0")
    assert db.designs["s1"]["report"]["status"] == "eligible"
    assert results == [{"id": "s1", "challenge": "rms", "status": "eligible", "official": True, "score": 1.25}]


def test_unofficial_result_gets_no_score():
    db = FakeSupabase()
    db.add("s1", "c-rms")
    run(db, lambda p, c: {**report(official=False), "unofficial_score": 1.25})
    s = db.submissions["s1"]
    assert (s["status"], s["official"], s["score"], s["is_valid"]) == ("eligible", False, None, False)


def test_failed_design_gets_status_and_reasons():
    db = FakeSupabase()
    db.add("s1", "c-dbl")
    run(db, lambda p, c: report("constraint_failed", violations=["EFL_mm: 90; required [99, 101].", "BFD_mm: 5"]))
    s = db.submissions["s1"]
    assert (s["status"], s["score"], s["is_valid"]) == ("constraint_failed", None, False)
    assert s["validation_error"].startswith("EFL_mm")


def test_unknown_status_becomes_evaluator_error():
    assert result_columns({"status": "weird"}, "2.1.0", "t")["status"] == "evaluator_error"


def test_resubmission_during_evaluation_discards_the_result():
    db = FakeSupabase()
    db.add("s1", "c-rms")

    def evaluate(p, c):
        db.submissions["s1"]["updated_at"] = NOW.isoformat()  # participant submits again
        return report()

    logs = []
    assert run(db, evaluate, logs) == []
    assert db.submissions["s1"]["status"] == "pending"
    assert db.submissions["s1"]["score"] is None
    assert any("discarded" in line for line in logs)


def test_missing_prescription_waits_then_fails():
    db = FakeSupabase()
    db.add("young", "c-rms", prescription=None, minutes_old=2)
    db.add("old", "c-rms", prescription=None, minutes_old=60)
    run(db, lambda p, c: pytest.fail("must not evaluate without a prescription"))
    assert db.submissions["young"]["status"] == "pending"
    assert db.submissions["old"]["status"] == "invalid_prescription"


def test_only_challenges_of_this_version_are_judged():
    db = FakeSupabase()
    db.add("s-old", "c-old")
    db.add("s-new", "c-new")
    db.add("s-done", "c-rms", status="eligible")
    logs = []
    run(db, lambda p, c: pytest.fail("nothing to judge"), logs)
    assert db.submissions["s-old"]["status"] == "pending"   # judged by the 2.0.0 job
    assert db.submissions["s-new"]["status"] == "pending"   # no slug mapping
    assert any("unknown-slug" in line for line in logs)


def test_real_evaluator_process_on_an_optiland_file():
    data = json.loads((ROOT / "examples" / "doublet.optiland.json").read_text(encoding="utf-8"))
    rep = run_evaluator(ROOT, data, "doublet")
    assert rep["status"] == "eligible", rep["violations"]
    assert rep["score"] == pytest.approx(0.18106844456019955, rel=1e-12)


def test_real_evaluator_process_reports_a_bad_file():
    rep = run_evaluator(ROOT, {"surface_group": {"surfaces": []}}, "doublet")
    assert rep["status"] == "invalid_prescription"


def test_main_without_secrets_does_nothing(monkeypatch, capsys):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    assert main(["--evaluator-dir", str(ROOT)]) == 0
    assert "not set" in capsys.readouterr().out
