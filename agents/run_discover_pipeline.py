"""Discover-stage step 3: pull a real, multi-day, multi-source batch, run it
through the Sense-stage agent, then cluster the resulting signals.

This produces the "real extracted-and-clustered output" that
evals/opportunity-scoring.md (still a SKELETON file) needs before it can be
hand-labeled — see CLAUDE.md's build order and that file's "Building this
eval set" section. This script does not write to that eval file; it only
prints clusters for human review.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.discover_agent import Cluster, cluster_signals  # noqa: E402
from agents.sense_agent import ExtractionResult, extract_signal  # noqa: E402
from sources import hn_client, stackexchange_client  # noqa: E402
from sources.models import Post  # noqa: E402

# Broadened beyond the original Sense-stage eval-labeling pull
# (sources/pull_candidates.py) to surface more cross-post corroboration —
# more tags/queries and higher per-call volume, plus serverfault as a
# secondary SE site per docs/data-sources.md ("consider relevant tags on
# serverfault and superuser as secondary sites").
SE_SECURITY_TAGS = [
    "phishing",
    "siem",
    "vulnerability-management",
    "incident-response",
    "malware",
    "compliance",
    "risk-assessment",
    "email",
]
SE_SERVERFAULT_TAGS = ["monitoring", "patch-management", "backup", "security"]
HN_QUERIES = [
    "alert fatigue",
    "SIEM",
    "MSP security",
    "phishing",
    "vulnerability management",
    "vulnerability scanner false positive",
    "third party risk",
    "compliance audit",
    "SOC analyst",
    "CVE prioritization",
    "patch management",
    "security alert noise",
]

DAYS_BACK = 365


def pull_batch(fromdate: int | None = None) -> list[Post]:
    """Pull posts across all configured tags/queries.

    `fromdate` (unix timestamp) lets callers pull incrementally since a
    prior run instead of always re-pulling the full trailing window — see
    agents/run_pipeline.py, which tracks a last-run cursor for exactly this.
    Defaults to the full DAYS_BACK-day window when not given, which is what
    this module's own eval-building use (agents/run_discover_pipeline.py's
    main()) wants.
    """
    if fromdate is None:
        fromdate = int(time.time()) - DAYS_BACK * 86400
    posts: list[Post] = []

    for tag in SE_SECURITY_TAGS:
        posts.extend(
            stackexchange_client.fetch_posts(
                site="security", tagged=tag, pagesize=20, fromdate=fromdate
            )
        )

    for tag in SE_SERVERFAULT_TAGS:
        posts.extend(
            stackexchange_client.fetch_posts(
                site="serverfault", tagged=tag, pagesize=15, fromdate=fromdate
            )
        )

    for query in HN_QUERIES:
        # Relevance-ranked search, not by_date: HN's date-sorted search drops
        # relevance ranking entirely and returns mostly unrelated recent
        # stories. Relevance search still spans days on its own, since the
        # matching posts it surfaces were created on different dates.
        posts.extend(
            hn_client.fetch_posts(query, hits_per_page=12, by_date=False, fetch_comments=True)
        )

    # De-dupe by permalink (tags/queries overlap).
    seen: set[str] = set()
    deduped: list[Post] = []
    for post in posts:
        if post.permalink in seen:
            continue
        seen.add(post.permalink)
        deduped.append(post)

    # HN's relevance-ranked /search (by_date=False, used above) has no
    # fromdate param at the API level, unlike the Stack Exchange calls above
    # — so without this, HN results ignore the window entirely and old
    # relevance-ranked hits leak into a supposedly-bounded pull. Apply the
    # cutoff uniformly, post-fetch, across every source.
    return [p for p in deduped if p.created_utc >= fromdate]


def extract_signals(posts: list[Post]) -> list[ExtractionResult]:
    signals: list[ExtractionResult] = []
    for i, post in enumerate(posts):
        try:
            result = extract_signal(post)
        except Exception as e:
            print(f"[SKIP] {post.permalink}: extraction failed: {e}")
            continue
        marker = "SIGNAL" if result.is_signal else "noise "
        print(f"[{i + 1}/{len(posts)}] [{marker}] {post.source} {post.permalink}")
        if result.is_signal:
            signals.append(result)
    return signals


def print_clusters(clusters: list[Cluster], signals: list[ExtractionResult]) -> None:
    by_permalink = {s.permalink: s for s in signals}

    print("\n" + "=" * 72)
    print(f"CLUSTERS ({len(clusters)} total, {len(signals)} signals)")
    print("=" * 72)

    multi = [c for c in clusters if len(c.signal_ids) > 1]
    singles = [c for c in clusters if len(c.signal_ids) == 1]
    cross_source = [
        c for c in multi if len({by_permalink[sid].source for sid in c.signal_ids}) > 1
    ]
    print(f"Multi-signal clusters: {len(multi)} (cross-source: {len(cross_source)})")
    print(f"Singleton clusters:    {len(singles)}\n")

    for c in clusters:
        print(f"--- {c.cluster_id} ({len(c.signal_ids)} signal(s)) ---")
        print(f"shared_pain_statement: {c.shared_pain_statement}")
        print(f"rationale: {c.rationale}")
        for sid in c.signal_ids:
            s = by_permalink.get(sid)
            if s is None:
                print(f"  - {sid}  (WARNING: id not found in signal set)")
                continue
            print(f"  - [{s.source}] {s.problem_statement}")
            print(f"    {sid}")
        print()


def main() -> None:
    print(f"Pulling posts from the last {DAYS_BACK} days across SE security tags "
          f"{SE_SECURITY_TAGS}, serverfault tags {SE_SERVERFAULT_TAGS}, "
          f"and HN queries {HN_QUERIES}...")
    posts = pull_batch()
    print(f"Pulled {len(posts)} unique posts.\n")

    print("Running Sense-stage extraction...")
    signals = extract_signals(posts)
    print(f"\n{len(signals)} of {len(posts)} posts judged is_signal=true.\n")

    if not signals:
        print("No signals extracted — nothing to cluster.")
        return

    print("Clustering signals...")
    clusters = cluster_signals(signals)
    print_clusters(clusters, signals)


if __name__ == "__main__":
    main()
