"""Scores agents/discover_agent.py:score_cluster against the real,
hand-labeled rows in evals/opportunity-scoring.md.

Same discipline as evals/run_evals.py: the eval file is the spec, so this
parses its "## Rows" table directly rather than duplicating ground truth.
For each row it re-fetches the member posts live from their permalinks,
re-runs Sense-stage extraction to reconstruct the ExtractionResults, then
runs score_cluster and compares against the hand-labeled values.

novelty and overall_rank_score are the two fields evals/opportunity-scoring.md
marks as DRAFT-only from the model (novelty is explicitly human-review-only
per the rubric); reports both per-field error and, for overall_rank_score,
whether the model's ranking of the batch agrees with the hand-labeled
ranking, per this stage's "Definition of done."
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.discover_agent import Cluster, score_cluster  # noqa: E402
from agents.sense_agent import ExtractionResult, extract_signal  # noqa: E402
from sources import hn_client, stackexchange_client  # noqa: E402

EVAL_FILE = Path(__file__).parent / "opportunity-scoring.md"

_LINK_RE = re.compile(r"\[[^\]]*\]\((https?://[^\)]+)\)")

FIELDS = [
    "signal_validity",
    "extraction_accuracy",
    "frequency_corroboration",
    "small_team_feasibility",
    "willingness_to_pay_signal",
    "novelty",
    "overall_rank_score",
]


@dataclass
class GroundTruthRow:
    cluster_id: str
    permalinks: list[str]
    opportunity_statement: str
    signal_validity: float
    extraction_accuracy: float
    frequency_corroboration: float
    small_team_feasibility: float
    willingness_to_pay_signal: float
    novelty: float
    overall_rank_score: float


def _split_row(line: str) -> list[str]:
    cells = line.strip().split("|")
    if cells and cells[0].strip() == "":
        cells = cells[1:]
    if cells and cells[-1].strip() == "":
        cells = cells[:-1]
    return [c.strip() for c in cells]


def parse_rows(text: str) -> list[GroundTruthRow]:
    start = text.index("## Rows")
    end = text.index("## Definition of done", start)
    section = text[start:end]
    lines = [
        line
        for line in section.splitlines()
        if line.strip().startswith("|") and "---" not in line
    ]
    data_lines = lines[1:]  # drop header row

    rows = []
    for line in data_lines:
        cells = _split_row(line)
        (
            cluster_id,
            signal_ids_cell,
            opportunity_statement,
            signal_validity,
            extraction_accuracy,
            frequency_corroboration,
            small_team_feasibility,
            willingness_to_pay_signal,
            novelty,
            overall_rank_score,
            _rationale,
        ) = cells[0:11]

        permalinks = _LINK_RE.findall(signal_ids_cell)
        rows.append(
            GroundTruthRow(
                cluster_id=cluster_id,
                permalinks=permalinks,
                opportunity_statement=opportunity_statement,
                signal_validity=float(signal_validity),
                extraction_accuracy=float(extraction_accuracy),
                frequency_corroboration=float(frequency_corroboration),
                small_team_feasibility=float(small_team_feasibility),
                willingness_to_pay_signal=float(willingness_to_pay_signal),
                novelty=float(novelty),
                overall_rank_score=float(overall_rank_score),
            )
        )
    return rows


def fetch_signal(permalink: str) -> ExtractionResult:
    if "stackexchange.com" in permalink or "serverfault.com" in permalink:
        post = stackexchange_client.fetch_post(permalink)
    elif "ycombinator.com" in permalink:
        post = hn_client.fetch_post(permalink)
    else:
        raise ValueError(f"Unknown source for permalink: {permalink}")
    return extract_signal(post)


def main() -> None:
    text = EVAL_FILE.read_text()
    rows = parse_rows(text)
    print(f"Loaded {len(rows)} ground-truth clusters\n")

    errors: dict[str, list[float]] = {f: [] for f in FIELDS}
    ranked: list[tuple[str, float, float]] = []  # cluster_id, ground_truth, predicted

    for row in rows:
        try:
            signals = [fetch_signal(p) for p in row.permalinks]
        except Exception as e:
            print(f"[SKIP] {row.cluster_id}: fetch/extraction failed: {e}")
            continue

        cluster = Cluster(
            cluster_id=row.cluster_id,
            signal_ids=row.permalinks,
            shared_pain_statement=row.opportunity_statement,
            rationale="(ground-truth reconstruction — no clustering rationale)",
        )
        scored = score_cluster(cluster, signals)

        print(f"--- {row.cluster_id} ({len(signals)} signal(s)) ---")
        for field in FIELDS:
            truth = getattr(row, field)
            pred = getattr(scored, field)
            diff = abs(truth - pred)
            errors[field].append(diff)
            flag = "" if diff <= 0.15 else "  <-- >0.15 off"
            print(f"  {field:28s} truth={truth:.2f} pred={pred:.2f} diff={diff:.2f}{flag}")

        ranked.append((row.cluster_id, row.overall_rank_score, scored.overall_rank_score))
        print()

    print("=" * 72)
    print("SUMMARY (mean absolute error per field)")
    print("=" * 72)
    for field in FIELDS:
        vals = errors[field]
        if not vals:
            continue
        mae = sum(vals) / len(vals)
        print(f"  {field:28s} MAE={mae:.3f}  n={len(vals)}")

    if ranked:
        truth_order = [cid for cid, _, _ in sorted(ranked, key=lambda r: -r[1])]
        pred_order = [cid for cid, _, _ in sorted(ranked, key=lambda r: -r[2])]
        print("\nRank ordering by overall_rank_score:")
        print(f"  ground truth: {truth_order}")
        print(f"  predicted   : {pred_order}")
        # Simple rank-agreement metric: how many clusters keep the same
        # position in both orderings.
        agree = sum(1 for a, b in zip(truth_order, pred_order) if a == b)
        print(f"  exact position agreement: {agree}/{len(truth_order)}")

    print("\nDefinition of done (evals/opportunity-scoring.md):")
    print("  [ ] agent's overall_rank_score ordering roughly agrees with hand-labeled ranking — review printed orderings above manually")


if __name__ == "__main__":
    main()
