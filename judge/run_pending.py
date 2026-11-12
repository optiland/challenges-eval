"""Judge pending challenge submissions.

Runs in GitHub Actions (.github/workflows/judge.yml). For one evaluator
version (a checkout of a release tag) it:

1. reads the challenges whose ``evaluator_version`` is that version;
2. reads their pending submissions with the private design row;
3. runs ``challenge_evaluator.py`` of that tag on each prescription, in its
   own process with a timeout;
4. writes the report into ``competition_submission_designs`` and the result
   into ``competition_submissions``.

A write succeeds only if the row has not changed since it was read (same
``updated_at`` and still ``pending``). If a participant submits again while
the judge works, the old result is discarded and the next run judges the new
design.

The public log shows only submission ids, statuses and scores, never a
prescription or a report.

Environment: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY.
Standard library only.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
STATUSES = {
    "eligible", "invalid_prescription", "constraint_failed", "ray_validation_failed",
    "needs_numerical_review", "evaluator_error",
}
MISSING_DESIGN_GRACE_S = 15 * 60
EVALUATION_TIMEOUT_S = 30 * 60
MAX_SUMMARY_LEN = 1000


class Supabase:
    """Minimal PostgREST client with the service-role key."""

    def __init__(self, url: str, key: str):
        self.base = url.rstrip("/") + "/rest/v1/"
        self.headers = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    def _call(self, method: str, table: str, query: str, body: Any = None, prefer: str | None = None) -> Any:
        headers = dict(self.headers)
        if prefer:
            headers["Prefer"] = prefer
        data = None if body is None else json.dumps(body).encode("utf-8")
        req = urllib.request.Request(f"{self.base}{table}?{query}", data=data, method=method, headers=headers)
        with urllib.request.urlopen(req, timeout=60) as resp:
            text = resp.read().decode("utf-8")
        return json.loads(text) if text else None

    def select(self, table: str, query: str) -> list[dict]:
        return self._call("GET", table, query)

    def update(self, table: str, query: str, body: dict) -> list[dict]:
        """PATCH and return the changed rows (empty if no row matched)."""
        return self._call("PATCH", table, query, body, prefer="return=representation")


def q(value: str) -> str:
    """Quote a value for a PostgREST filter."""
    return urllib.parse.quote(str(value), safe="")


def evaluator_version(evaluator_dir: Path) -> str:
    text = (evaluator_dir / "challenge_evaluator.py").read_text(encoding="utf-8")
    match = re.search(r'^EVALUATOR_VERSION = "([^"]+)"', text, re.M)
    if not match:
        raise RuntimeError(f"No EVALUATOR_VERSION in {evaluator_dir}.")
    return match.group(1)


def run_evaluator(evaluator_dir: Path, prescription: Any, challenge: str) -> dict:
    """Run the CLI of the tagged evaluator in its own process."""
    with tempfile.TemporaryDirectory() as tmp:
        src, out = Path(tmp) / "submission.json", Path(tmp) / "report.json"
        src.write_text(json.dumps(prescription), encoding="utf-8")
        try:
            proc = subprocess.run(
                [sys.executable, str(evaluator_dir / "challenge_evaluator.py"), str(src),
                 "--challenge", challenge, "--output", str(out)],
                cwd=evaluator_dir, capture_output=True, text=True, timeout=EVALUATION_TIMEOUT_S, check=False,
                env={**os.environ, "MPLBACKEND": "Agg"},
            )
        except subprocess.TimeoutExpired:
            return {"status": "evaluator_error", "official": False, "score": None,
                    "violations": [f"The evaluation did not finish within {EVALUATION_TIMEOUT_S // 60} minutes."]}
        if out.exists():
            return json.loads(out.read_text(encoding="utf-8"))
        tail = (proc.stderr or "")[-1500:]
        return {"status": "evaluator_error", "official": False, "score": None,
                "violations": [f"The evaluator stopped without a report (exit code {proc.returncode})."],
                "stderr_tail": tail}


def result_columns(report: dict, version: str, now: str) -> dict:
    """Columns of competition_submissions for one report."""
    status = report.get("status")
    if status not in STATUSES:
        status = "evaluator_error"
    official = bool(report.get("official"))
    score = report.get("score") if status == "eligible" and official else None
    violations = [str(v) for v in report.get("violations") or []]
    return {
        "status": status,
        "official": official,
        "score": score,
        "is_valid": score is not None,
        "evaluator_version": version,
        "evaluated_at": now,
        "validation_error": "; ".join(violations)[:MAX_SUMMARY_LEN] or None,
    }


def _age_seconds(created_at: str | None, now: dt.datetime) -> float:
    if not created_at:
        return float("inf")
    created = dt.datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    return (now - created).total_seconds()


def _design(row: dict) -> dict | None:
    embed = row.get("competition_submission_designs")
    if isinstance(embed, list):
        return embed[0] if embed else None
    return embed


def judge_pending(client, version: str, slug_to_challenge: dict[str, str],
                  evaluate: Callable[[Any, str], dict], limit: int = 50,
                  now: dt.datetime | None = None, log: Callable[[str], None] = print) -> list[dict]:
    """Judge pending submissions of the challenges that use ``version``."""
    now = now or dt.datetime.now(dt.timezone.utc)
    now_iso = now.isoformat()
    competitions = client.select("competitions", f"select=id,slug&evaluator_version=eq.{q(version)}")
    challenge_of = {}
    for comp in competitions:
        challenge = slug_to_challenge.get(comp["slug"])
        if challenge:
            challenge_of[comp["id"]] = challenge
        else:
            log(f"warning: no evaluator challenge for slug {comp['slug']!r}; add it to judge/challenges.json")
    if not challenge_of:
        log(f"No challenges use evaluator {version}.")
        return []
    ids = ",".join(q(i) for i in challenge_of)
    rows = client.select(
        "competition_submissions",
        "select=id,competition_id,created_at,updated_at,"
        "competition_submission_designs(prescription,updated_at)"
        f"&status=eq.pending&competition_id=in.({ids})&order=created_at.asc&limit={int(limit)}",
    )
    results = []
    for row in rows:
        sub_id, challenge = row["id"], challenge_of[row["competition_id"]]
        design = _design(row)
        if design is None:
            if _age_seconds(row.get("created_at"), now) < MISSING_DESIGN_GRACE_S:
                log(f"{sub_id}: no prescription yet, waiting")
                continue
            report = {"status": "invalid_prescription", "official": False, "score": None,
                      "violations": ["No prescription was submitted."]}
        else:
            report = evaluate(design["prescription"], challenge)
            stamp = q(design["updated_at"])
            client.update("competition_submission_designs",
                          f"submission_id=eq.{q(sub_id)}&updated_at=eq.{stamp}", {"report": report})
        columns = result_columns(report, version, now_iso)
        guard = f"updated_at=eq.{q(row['updated_at'])}" if row.get("updated_at") else "updated_at=is.null"
        changed = client.update("competition_submissions", f"id=eq.{q(sub_id)}&status=eq.pending&{guard}", columns)
        if not changed:
            log(f"{sub_id}: changed during evaluation, result discarded (judged again next run)")
            continue
        results.append({"id": sub_id, "challenge": challenge, "status": columns["status"],
                        "official": columns["official"], "score": columns["score"]})
        log(f"{sub_id}: {challenge} {columns['status']} score={columns['score']}")
    return results


def _summary(results: list[dict], version: str) -> str:
    lines = [f"### Judge, evaluator {version}", "", f"Judged: {len(results)}", ""]
    if results:
        lines += ["| Submission | Challenge | Status | Score |", "|---|---|---|---|"]
        lines += [f"| `{r['id']}` | {r['challenge']} | {r['status']} | {r['score'] if r['score'] is not None else ''} |"
                  for r in results]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--evaluator-dir", type=Path, required=True, help="checkout of an evaluator release tag")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args(argv)
    url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY is not set; nothing to do.")
        return 0
    evaluator_dir = args.evaluator_dir.resolve()
    version = evaluator_version(evaluator_dir)
    slugs = json.loads((HERE / "challenges.json").read_text(encoding="utf-8"))
    try:
        results = judge_pending(Supabase(url, key), version, slugs,
                                lambda p, c: run_evaluator(evaluator_dir, p, c), limit=args.limit)
    except urllib.error.HTTPError as exc:
        print(f"Supabase request failed: HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')[:500]}")
        return 1
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(_summary(results, version))
    return 0


if __name__ == "__main__":
    sys.exit(main())
