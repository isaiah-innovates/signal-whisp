"""Full daily pipeline: ingest -> Sense -> Discover (cluster + score) -> Deliver.

Build-order step 6 (delivery layer, digest half only — see docs/architecture.md
and docs/progress.md for why the query interface/web app is a separate, later
piece). Reuses pull_batch/extract_signals from run_discover_pipeline.py (which
stays focused on its original eval-building purpose) and adds scoring,
persistence, and a rendered markdown digest on top.

Each run persists three immutable JSONL files under data/runs/<run_id>/ (raw
posts, Sense-stage signals, Discover-stage scored clusters) per
docs/architecture.md's "raw text should never be overwritten by downstream
processing" — a re-run on the same day overwrites that day's own files, but
never a prior day's. The rendered digest goes to reports/<run_id>.md.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.discover_agent import Cluster, ScoredCluster, cluster_signals, score_cluster  # noqa: E402
from agents.run_discover_pipeline import extract_signals, pull_batch  # noqa: E402
from agents.sense_agent import ExtractionResult  # noqa: E402
from sources.models import Post  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data" / "runs"
REPORTS_DIR = REPO_ROOT / "reports"


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


def render_digest(run_id: str, scored_clusters: list[ScoredCluster]) -> str:
    """Rank by overall_rank_score (DRAFT — see docs/progress.md's "Scoring
    design" section for current calibration and known gaps) and render a
    ranked markdown digest.
    """
    ranked = sorted(scored_clusters, key=lambda c: -c.overall_rank_score)

    lines = [
        f"# Signal digest — {run_id}",
        "",
        f"{len(ranked)} candidate opportunities, ranked by `overall_rank_score`.",
        "`novelty` is DRAFT/human-review-only per `evals/opportunity-scoring.md`'s "
        "rubric — do not treat it as final. `overall_rank_score` is a "
        "calibrated-but-unproven formula; see `docs/progress.md`'s "
        "\"Scoring design\" section for current accuracy and known gaps.",
        "",
    ]

    for i, c in enumerate(ranked, 1):
        lines.append(f"## {i}. {c.opportunity_statement}")
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
        lines.append(f"_{c.rationale}_")
        lines.append("")
        lines.append("Signals:")
        for sid in c.signal_ids:
            lines.append(f"- {sid}")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    run_id = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    run_dir = DATA_DIR / run_id

    print(f"=== Pipeline run {run_id} ===\n")

    posts: list[Post] = pull_batch()
    print(f"Pulled {len(posts)} unique posts.")
    _write_jsonl(run_dir / "posts.jsonl", posts)

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

    digest = render_digest(run_id, scored_clusters)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / f"{run_id}.md"
    report_path.write_text(digest)

    print(f"\nWrote digest to {report_path}")
    print(f"Wrote raw data to {run_dir}/")


if __name__ == "__main__":
    main()
