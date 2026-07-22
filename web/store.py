"""Loads and filters historical Discover/Decide-stage output from
data/runs/*/{clusters,decisions}.jsonl.

No database yet — Postgres arrives at the Railway deployment step per
CLAUDE.md's stack conventions, not before. This reads directly off the
JSONL artifacts agents/run_pipeline.py already writes per run.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from agents.decide_agent import DecideResult
from agents.discover_agent import ScoredCluster

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "runs"


@dataclass
class PersistedCluster:
    run_id: str  # YYYY-MM-DD, the run's directory name
    cluster: ScoredCluster
    decision: DecideResult | None  # None if decisions.jsonl is missing/older run or classification failed


def _load_decisions(run_dir: Path) -> dict[str, DecideResult]:
    decisions_path = run_dir / "decisions.jsonl"
    if not decisions_path.exists():
        return {}
    by_cluster_id = {}
    for line in decisions_path.read_text().splitlines():
        if not line.strip():
            continue
        fields = json.loads(line)
        by_cluster_id[fields["cluster_id"]] = DecideResult(**fields)
    return by_cluster_id


def load_all_clusters(data_dir: Path = DATA_DIR) -> list[PersistedCluster]:
    """Read every run's clusters.jsonl (+ decisions.jsonl if present),
    tagging each row with its run_id and matching decision.

    run_id strings are YYYY-MM-DD, so plain string comparison is a valid
    date-range filter — no date parsing needed. Older runs predating the
    Decide-stage wiring have no decisions.jsonl at all; decision is None
    for those rather than raising.
    """
    records: list[PersistedCluster] = []
    if not data_dir.exists():
        return records

    for run_dir in sorted(data_dir.iterdir()):
        clusters_path = run_dir / "clusters.jsonl"
        if not clusters_path.exists():
            continue
        decisions = _load_decisions(run_dir)
        for line in clusters_path.read_text().splitlines():
            if not line.strip():
                continue
            fields = json.loads(line)
            cluster = ScoredCluster(**fields)
            records.append(
                PersistedCluster(
                    run_id=run_dir.name,
                    cluster=cluster,
                    decision=decisions.get(cluster.cluster_id),
                )
            )
    return records


def filter_clusters(
    records: list[PersistedCluster],
    date_from: str | None = None,
    date_to: str | None = None,
    min_score: float | None = None,
    q: str | None = None,
    decide_action: str | None = None,
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
    if decide_action:
        out = [r for r in out if r.decision is not None and r.decision.decide_action == decide_action]
    return sorted(out, key=lambda r: -r.cluster.overall_rank_score)
