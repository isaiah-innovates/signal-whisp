"""Scores agents/sense_agent.py against the real, hand-labeled rows in
evals/signal-extraction.md.

The eval file is the spec: this script parses its markdown tables directly
rather than duplicating ground truth into a second format, so there is only
one place labels can drift. It re-fetches each row's post content live from
its permalink (the eval file stores labels, not full post bodies), runs the
Sense-stage agent, and reports accuracy against the definition of done in
§7: is_signal accuracy >= 90%, zero false positives on noise rows, and
adversarial cases handled on manual review of the printed side-by-sides.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.sense_agent import extract_signal  # noqa: E402
from sources import hn_client, stackexchange_client  # noqa: E402
from sources.models import Post  # noqa: E402

EVAL_FILE = Path(__file__).parent / "signal-extraction.md"

_LINK_RE = re.compile(r"\[[^\]]*\]\((https?://[^\)]+)\)")


@dataclass
class GroundTruthRow:
    row_num: str
    permalink: str
    source: str
    is_signal: bool
    problem_statement: str | None = None
    adversarial_case: str | None = None


def _split_row(line: str) -> list[str]:
    cells = line.strip().split("|")
    # Leading/trailing empty strings from the outer pipes
    if cells and cells[0].strip() == "":
        cells = cells[1:]
    if cells and cells[-1].strip() == "":
        cells = cells[:-1]
    return [c.strip() for c in cells]


def _extract_table(text: str, start_heading: str, end_heading: str) -> list[str]:
    start = text.index(start_heading) + len(start_heading)
    end = text.index(end_heading, start)
    section = text[start:end]
    lines = [
        line
        for line in section.splitlines()
        if line.strip().startswith("|") and "---" not in line
    ]
    return lines[1:]  # drop header row, keep data rows


def _first_permalink(cell: str) -> str:
    match = _LINK_RE.search(cell)
    if not match:
        raise ValueError(f"No permalink found in cell: {cell!r}")
    return match.group(1)


def parse_signal_rows(text: str) -> list[GroundTruthRow]:
    lines = _extract_table(text, "## 3. Signal rows", "## 4. Noise rows")
    rows = []
    for line in lines:
        cells = _split_row(line)
        row_num, permalink_cell, source, is_signal, problem_statement = cells[0:5]
        adversarial_case = None
        match = re.search(r"Adversarial case #(\d+)", problem_statement)
        if match:
            adversarial_case = match.group(1)
        rows.append(
            GroundTruthRow(
                row_num=row_num,
                permalink=_first_permalink(permalink_cell),
                source=source,
                is_signal=is_signal.strip().lower() == "true",
                problem_statement=problem_statement,
                adversarial_case=adversarial_case,
            )
        )
    return rows


def parse_noise_rows(text: str) -> list[GroundTruthRow]:
    lines = _extract_table(text, "## 4. Noise rows", "## 5. Adversarial cases")
    rows = []
    for line in lines:
        cells = _split_row(line)
        row_num, permalink_cell, source, is_signal, rationale = cells[0:5]
        adversarial_case = None
        match = re.search(r"adversarial case #(\d+)", rationale, re.IGNORECASE)
        if match:
            adversarial_case = match.group(1)
        rows.append(
            GroundTruthRow(
                row_num=row_num,
                permalink=_first_permalink(permalink_cell),
                source=source,
                is_signal=is_signal.strip().lower() == "true",
                adversarial_case=adversarial_case,
            )
        )
    return rows


def fetch_post(source: str, permalink: str) -> Post:
    if source == "stackexchange":
        return stackexchange_client.fetch_post(permalink)
    if source == "hackernews":
        return hn_client.fetch_post(permalink)
    raise ValueError(f"Unknown source: {source}")


def main() -> None:
    text = EVAL_FILE.read_text()
    signal_rows = parse_signal_rows(text)
    noise_rows = parse_noise_rows(text)
    all_rows = signal_rows + noise_rows

    print(f"Loaded {len(signal_rows)} signal rows, {len(noise_rows)} noise rows\n")

    tp = fp = tn = fn = 0
    noise_false_positives: list[GroundTruthRow] = []
    adversarial_results: list[tuple[GroundTruthRow, bool, str | None]] = []

    for row in all_rows:
        try:
            post = fetch_post(row.source, row.permalink)
        except Exception as e:
            print(f"[SKIP] row {row.row_num} ({row.permalink}): fetch failed: {e}")
            continue

        result = extract_signal(post)
        correct = result.is_signal == row.is_signal

        if row.is_signal and result.is_signal:
            tp += 1
        elif row.is_signal and not result.is_signal:
            fn += 1
        elif not row.is_signal and result.is_signal:
            fp += 1
            noise_false_positives.append(row)
        else:
            tn += 1

        marker = "OK " if correct else "FAIL"
        print(f"[{marker}] row {row.row_num} ({row.source}) expected={row.is_signal} got={result.is_signal}  {row.permalink}")

        if row.adversarial_case:
            adversarial_results.append((row, result.is_signal, result.problem_statement))

        if row.is_signal and result.is_signal:
            print(f"        ground truth : {row.problem_statement[:160]}")
            print(f"        model output : {result.problem_statement[:160] if result.problem_statement else '(null)'}")

    total = tp + fp + tn + fn
    accuracy = (tp + tn) / total if total else 0.0

    print("\n" + "=" * 72)
    print("SUMMARY")
    print("=" * 72)
    print(f"Total rows scored : {total}")
    print(f"is_signal accuracy: {accuracy:.1%}  (target: >= 90%)")
    print(f"Confusion matrix  : TP={tp} FP={fp} TN={tn} FN={fn}")

    if noise_false_positives:
        print(f"\nFALSE POSITIVES ON NOISE ROWS (target: 0): {len(noise_false_positives)}")
        for row in noise_false_positives:
            print(f"  - row {row.row_num}: {row.permalink}")
    else:
        print("\nFalse positives on noise rows: 0 (meets the zero-FP bar)")

    if adversarial_results:
        print(f"\nADVERSARIAL CASES — spot-check against evals/signal-extraction.md §5:")
        for row, predicted_is_signal, problem_statement in adversarial_results:
            print(f"  - case #{row.adversarial_case}, row {row.row_num}: predicted is_signal={predicted_is_signal}")
            if problem_statement:
                print(f"      extracted: {problem_statement[:160]}")

    print("\nDefinition of done (evals/signal-extraction.md §7):")
    print(f"  [{'x' if accuracy >= 0.9 else ' '}] is_signal accuracy >= 90%")
    print(f"  [{'x' if not noise_false_positives else ' '}] zero false positives on noise rows")
    print("  [ ] adversarial rows 9-14 handled per stated correct behavior — review printed output above manually")


if __name__ == "__main__":
    main()
