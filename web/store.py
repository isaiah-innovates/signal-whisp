"""Loads and filters historical Discover-stage output from data/runs/*/clusters.jsonl.

No database yet — Postgres arrives at the Railway deployment step per
CLAUDE.md's stack conventions, not before. This reads directly off the
JSONL artifacts agents/run_pipeline.py already writes per run.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from agents.discover_agent import ScoredCluster

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "runs"


@dataclass
class PersistedCluster:
    run_id: str  # YYYY-MM-DD, the run's directory name
    cluster: ScoredCluster


def load_all_clusters(data_dir: Path = DATA_DIR) -> list[PersistedCluster]:
    """Read every run's clusters.jsonl, tagging each row with its run_id.

    run_id strings are YYYY-MM-DD, so plain string comparison is a valid
    date-range filter — no date parsing needed.
    """
    records: list[PersistedCluster] = []
    if not data_dir.exists():
        return records

    for run_dir in sorted(data_dir.iterdir()):
        clusters_path = run_dir / "clusters.jsonl"
        if not clusters_path.exists():
            continue
        for line in clusters_path.read_text().splitlines():
            if not line.strip():
                continue
            fields = json.loads(line)
            records.append(PersistedCluster(run_id=run_dir.name, cluster=ScoredCluster(**fields)))
    return records


def filter_clusters(
    records: list[PersistedCluster],
    date_from: str | None = None,
    date_to: str | None = None,
    min_score: float | None = None,
    q: str | None = None,
) -> list[PersistedCluster]:
    """Filter and rank by overall_rank_score descending."""
    out = records
    if date_from:
        out = [r for r in out if r.run_id >= date_from]
    if date_to:
        out = [r for r in out if r.run_id <= date_to]
    if min_score is not None:
        out = [r for r in out if r.cluster.overall_rank_score >= min_score]
    if q:
        needle = q.lower()
        out = [
            r
            for r in out
            if needle in r.cluster.opportunity_statement.lower()
            or needle in r.cluster.rationale.lower()
        ]
    return sorted(out, key=lambda r: -r.cluster.overall_rank_score)
