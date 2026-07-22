"""Query API + minimal dashboard over historical Discover/Decide-stage output.

Build-order step 6, second half — docs/architecture.md's "/web/ query API +
minimal dashboard". Reads data/runs/*/{clusters,decisions}.jsonl written by
agents/run_pipeline.py; no database yet, per CLAUDE.md's stack conventions
(Postgres arrives at the Railway deployment step, not before).

Run with: uvicorn web.app:app --reload   (from the repo root)
"""

from __future__ import annotations

import sys
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from web.store import filter_clusters, load_all_clusters  # noqa: E402

app = FastAPI(title="Signal — opportunity query API")

_web_dir = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(_web_dir / "templates"))
app.mount("/static", StaticFiles(directory=str(_web_dir / "static")), name="static")


@app.get("/api/runs")
def list_runs() -> list[str]:
    """All run_ids (YYYY-MM-DD) that have persisted clusters, newest first."""
    records = load_all_clusters()
    return sorted({r.run_id for r in records}, reverse=True)


@app.get("/api/clusters")
def api_clusters(
    date_from: str | None = None,
    date_to: str | None = None,
    min_score: float | None = None,
    q: str | None = None,
    decide_action: str | None = None,
) -> list[dict]:
    """Scored clusters across all runs, filtered and ranked by overall_rank_score.

    decide_action/rationale are included when a matching decisions.jsonl
    entry exists for that run; both are null for runs predating the
    Decide-stage wiring or a failed classification.
    """
    records = load_all_clusters()
    filtered = filter_clusters(records, date_from, date_to, min_score, q, decide_action)
    return [
        {
            "run_id": r.run_id,
            **asdict(r.cluster),
            "decide_action": r.decision.decide_action if r.decision else None,
            "decide_rationale": r.decision.rationale if r.decision else None,
        }
        for r in filtered
    ]


@app.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request,
    date_from: str | None = None,
    date_to: str | None = None,
    min_score: float | None = None,
    q: str | None = None,
    decide_action: str | None = None,
) -> HTMLResponse:
    records = load_all_clusters()
    filtered = filter_clusters(records, date_from, date_to, min_score, q, decide_action)
    run_ids = sorted({r.run_id for r in records}, reverse=True)
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "clusters": filtered,
            "total_all_time": len(records),
            "run_count": len(run_ids),
            "filters": {
                "date_from": date_from or "",
                "date_to": date_to or "",
                "min_score": "" if min_score is None else min_score,
                "q": q or "",
                "decide_action": decide_action or "",
            },
        },
    )
