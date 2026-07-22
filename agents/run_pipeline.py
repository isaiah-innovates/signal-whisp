"""Full daily pipeline: ingest -> Sense -> Discover (cluster + score) -> Decide -> Deliver.

Build-order step 6 (delivery layer digest) plus step 8's Decide-stage
classification, now wired together — see docs/architecture.md and
docs/progress.md for why the query interface/web app is a separate, later
piece. Reuses pull_batch/extract_signals from run_discover_pipeline.py (which
stays focused on its original eval-building purpose) and adds scoring,
classification, persistence, and a rendered markdown digest on top.

Each run persists four immutable JSONL files under data/runs/<run_id>/ (raw
posts, Sense-stage signals, Discover-stage scored clusters, Decide-stage
decisions) per docs/architecture.md's "raw text should never be overwritten
by downstream processing" — a re-run on the same day overwrites that day's
own files, but never a prior day's. The rendered digest goes to
reports/<run_id>.md, grouped by decide_action (pursue/watch/discard) rather
than a single flat ranked list.

Pulls incrementally since the last successful run (data/last_run.json)
rather than always re-pulling pull_batch's full 365-day window — otherwise
every repeat run re-fetches and re-extracts nearly the same posts, which is
most of this pipeline's real per-run cost (see docs/progress.md's Railway
cost estimate). First run (no cursor yet) falls back to the full window.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.decide_agent import DecideResult, classify_cluster  # noqa: E402
from agents.discover_agent import Cluster, ScoredCluster, cluster_signals, score_cluster  # noqa: E402
from agents.run_discover_pipeline import extract_signals, pull_batch  # noqa: E402
from agents.sense_agent import ExtractionResult  # noqa: E402
from sources.models import Post  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data" / "runs"
REPORTS_DIR = REPO_ROOT / "reports"
LAST_RUN_FILE = REPO_ROOT / "data" / "last_run.json"

# Subtracted from the recorded last-run timestamp before using it as the next
# fromdate, to cover indexing lag (a post created just before the previous
# run may not have been searchable/indexed yet by SE/HN at pull time) and
# clock skew between this machine and the two APIs.
OVERLAP_SECONDS = 3600

_ACTION_ORDER = ["pursue", "watch", "discard"]
_ACTION_HEADINGS = {
    "pursue": "Pursue",
    "watch": "Watch",
    "discard": "Discard",
}


def _load_last_run_at() -> int | None:
    if not LAST_RUN_FILE.exists():
        return None
    return json.loads(LAST_RUN_FILE.read_text())["last_run_at"]


def _save_last_run_at(ts: int) -> None:
    LAST_RUN_FILE.parent.mkdir(parents=True, exist_ok=True)
    LAST_RUN_FILE.write_text(json.dumps({"last_run_at": ts}))


def _write_jsonl(path: Path, records: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for r in records:
            f.write(json.dumps(asdict(r)) + "\n")


def score_clusters(
    clusters: list[Cluster], signals: list[ExtractionResult]
) -> list[ScoredCluster]:
    by_permalink = {s.permalink: s for s in signals}
    scored = []
    for cluster in clusters:
        members = [by_permalink[sid] for sid in cluster.signal_ids]
        try:
            scored.append(score_cluster(cluster, members))
        except Exception as e:
            print(f"[SKIP] {cluster.cluster_id}: scoring failed: {e}")
    return scored


def decide_clusters(scored_clusters: list[ScoredCluster]) -> list[DecideResult]:
    decisions = []
    for cluster in scored_clusters:
        try:
            decisions.append(classify_cluster(cluster))
        except Exception as e:
            print(f"[SKIP] {cluster.cluster_id}: decide classification failed: {e}")
    return decisions


def render_digest(
    run_id: str,
    scored_clusters: list[ScoredCluster],
    decisions: list[DecideResult],
) -> str:
    """Group by decide_action (pursue/watch/discard — see
    evals/decide-classification.md and docs/progress.md's "Decide-stage
    design" section), ranking by overall_rank_score within each group.

    A cluster whose classification failed (see decide_clusters) or whose
    cluster_id has no matching decision falls back into its own
    "Unclassified" section rather than being silently dropped from the
    digest.
    """
    decision_by_id = {d.cluster_id: d for d in decisions}

    buckets: dict[str, list[ScoredCluster]] = {action: [] for action in _ACTION_ORDER}
    unclassified: list[ScoredCluster] = []
    for c in scored_clusters:
        decision = decision_by_id.get(c.cluster_id)
        if decision is None:
            unclassified.append(c)
        else:
            buckets[decision.decide_action].append(c)

    lines = [
        f"# Signal digest — {run_id}",
        "",
        f"{len(scored_clusters)} candidate opportunities, grouped by Decide-stage "
        "`decide_action` (pursue/watch/discard), ranked by `overall_rank_score` "
        "within each group.",
        "`novelty` is DRAFT/human-review-only per `evals/opportunity-scoring.md`'s "
        "rubric — do not treat it as final. `overall_rank_score` is a "
        "calibrated-but-unproven formula, and `decide_action` is an eval-passing "
        "(19/21) but LLM-judged classification, not a certainty; see "
        "`docs/progress.md`'s \"Scoring design\" and \"Decide-stage design\" "
        "sections for current accuracy and known gaps.",
        "",
    ]

    def render_cluster(c: ScoredCluster, decision: DecideResult | None) -> None:
        lines.append(f"### {c.opportunity_statement}")
        lines.append("")
        lines.append(
            f"**overall_rank_score: {c.overall_rank_score:.2f}**  "
            f"(signal_validity={c.signal_validity:.2f}, "
            f"extraction_accuracy={c.extraction_accuracy:.2f}, "
            f"frequency_corroboration={c.frequency_corroboration:.2f}, "
            f"small_team_feasibility={c.small_team_feasibility:.2f}, "
            f"willingness_to_pay_signal={c.willingness_to_pay_signal:.2f}, "
            f"novelty={c.novelty:.2f} [DRAFT])"
        )
        lines.append("")
        if decision is not None:
            lines.append(f"**Decide: {decision.decide_action}** — {decision.rationale}")
            lines.append("")
        lines.append(f"_{c.rationale}_")
        lines.append("")
        lines.append("Signals:")
        for sid in c.signal_ids:
            lines.append(f"- {sid}")
        lines.append("")

    for action in _ACTION_ORDER:
        cluster_list = sorted(buckets[action], key=lambda c: -c.overall_rank_score)
        lines.append(f"## {_ACTION_HEADINGS[action]} ({len(cluster_list)})")
        lines.append("")
        if not cluster_list:
            lines.append("_None this run._")
            lines.append("")
            continue
        for c in cluster_list:
            render_cluster(c, decision_by_id[c.cluster_id])

    if unclassified:
        lines.append(f"## Unclassified ({len(unclassified)})")
        lines.append("")
        lines.append("_Decide-stage classification failed for these — see run logs._")
        lines.append("")
        for c in sorted(unclassified, key=lambda c: -c.overall_rank_score):
            render_cluster(c, None)

    return "\n".join(lines)


def main() -> None:
    run_id = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    run_dir = DATA_DIR / run_id

    print(f"=== Pipeline run {run_id} ===\n")

    last_run_at = _load_last_run_at()
    if last_run_at is None:
        print("No prior run recorded — pulling the full trailing 365-day window.")
        fromdate = None
    else:
        fromdate = last_run_at - OVERLAP_SECONDS
        since = datetime.fromtimestamp(fromdate, tz=timezone.utc).isoformat()
        print(f"Incremental pull: fetching posts since {since} "
              f"(last run + {OVERLAP_SECONDS}s overlap buffer).")

    posts: list[Post] = pull_batch(fromdate=fromdate)
    pull_completed_at = int(time.time())
    print(f"Pulled {len(posts)} unique posts.")
    _write_jsonl(run_dir / "posts.jsonl", posts)
    # Advance the cursor as soon as the pull itself succeeds — a downstream
    # Sense/Discover/Decide failure on an individual post is already handled
    # per-item (see [SKIP] logging below) and shouldn't cause next run to
    # re-fetch posts we've already pulled and stored.
    _save_last_run_at(pull_completed_at)

    signals = extract_signals(posts)
    print(f"\n{len(signals)} of {len(posts)} posts judged is_signal=true.")
    _write_jsonl(run_dir / "signals.jsonl", signals)

    if not signals:
        print("No signals extracted — nothing to cluster or score.")
        return

    clusters = cluster_signals(signals)
    print(f"Clustered into {len(clusters)} clusters.")

    scored_clusters = score_clusters(clusters, signals)
    print(f"Scored {len(scored_clusters)} of {len(clusters)} clusters.")
    _write_jsonl(run_dir / "clusters.jsonl", scored_clusters)

    decisions = decide_clusters(scored_clusters)
    print(f"Classified {len(decisions)} of {len(scored_clusters)} clusters.")
    _write_jsonl(run_dir / "decisions.jsonl", decisions)

    digest = render_digest(run_id, scored_clusters, decisions)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / f"{run_id}.md"
    report_path.write_text(digest)

    print(f"\nWrote digest to {report_path}")
    print(f"Wrote raw data to {run_dir}/")


if __name__ == "__main__":
    main()
