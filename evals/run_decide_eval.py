"""Scores agents/decide_agent.py:classify_cluster against the real,
hand-labeled rows in evals/decide-classification.md.

Unlike evals/run_discover_scoring_eval.py, this doesn't re-fetch posts or
re-run Sense/Discover — decide-classification.md's rows were pulled
directly from an already-persisted data/runs/<run_id>/clusters.jsonl, so
this reads that file back to reconstruct each row's exact ScoredCluster
input. That keeps the only source of variance in this eval the Decide
agent's own classification, not upstream re-extraction noise.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.decide_agent import classify_cluster  # noqa: E402
from agents.discover_agent import ScoredCluster  # noqa: E402

EVAL_FILE = Path(__file__).parent / "decide-classification.md"
DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "runs"


@dataclass
class GroundTruthRow:
    cluster_id: str
    run_id: str
    decide_action: str
    rationale: str


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
        cluster_id, run_id, _signal_ids, _opportunity_statement, _score, decide_action, rationale = cells[0:7]
        rows.append(
            GroundTruthRow(
                cluster_id=cluster_id,
                run_id=run_id,
                decide_action=decide_action,
                rationale=rationale,
            )
        )
    return rows


def load_scored_cluster(run_id: str, cluster_id: str) -> ScoredCluster:
    clusters_path = DATA_DIR / run_id / "clusters.jsonl"
    for line in clusters_path.read_text().splitlines():
        if not line.strip():
            continue
        fields = json.loads(line)
        if fields["cluster_id"] == cluster_id:
            return ScoredCluster(**fields)
    raise ValueError(f"{cluster_id} not found in {clusters_path}")


def main() -> None:
    text = EVAL_FILE.read_text()
    rows = parse_rows(text)
    print(f"Loaded {len(rows)} ground-truth rows\n")

    correct = 0
    confusion: dict[tuple[str, str], int] = {}
    mismatches = []

    for row in rows:
        cluster = load_scored_cluster(row.run_id, row.cluster_id)
        result = classify_cluster(cluster)

        match = result.decide_action == row.decide_action
        correct += match
        confusion[(row.decide_action, result.decide_action)] = (
            confusion.get((row.decide_action, result.decide_action), 0) + 1
        )

        flag = "" if match else "  <-- MISMATCH"
        print(f"{row.cluster_id:12s} truth={row.decide_action:8s} pred={result.decide_action:8s}{flag}")
        if not match:
            mismatches.append((row, result))

    print("\n" + "=" * 72)
    print(f"SUMMARY: {correct}/{len(rows)} exact match ({correct / len(rows):.1%})")
    print("=" * 72)

    print("\nConfusion (truth -> predicted): count")
    for (truth, pred), count in sorted(confusion.items()):
        marker = "" if truth == pred else "  <--"
        print(f"  {truth:8s} -> {pred:8s}: {count}{marker}")

    if mismatches:
        print("\nMismatches (truth rationale vs. predicted rationale):")
        for row, result in mismatches:
            print(f"\n--- {row.cluster_id} ---")
            print(f"  truth ({row.decide_action}): {row.rationale}")
            print(f"  pred  ({result.decide_action}): {result.rationale}")

    print("\nDefinition of done (evals/decide-classification.md):")
    print("  [ ] exact-match agreement high enough that disagreements read as genuine boundary calls")
    print("  [ ] off-mission scope pruning (cluster-7/8/9) still discarded by the agent's own reasoning")


if __name__ == "__main__":
    main()
