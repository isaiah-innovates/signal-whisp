"""One-off script: pull a real candidate batch from Stack Exchange + HN for
hand-labeling into evals/signal-extraction.md. Not part of the daily pipeline.
"""

from __future__ import annotations

import argparse
import json
import sys

from dotenv import load_dotenv

from sources import hn_client, stackexchange_client
from sources.models import Post

load_dotenv()

SE_TAGS = ["phishing", "siem", "vulnerability-management"]
HN_QUERIES = ["alert fatigue", "SIEM", "MSP security", "phishing", "vulnerability management"]


def pull_se(pagesize: int) -> list[Post]:
    posts: list[Post] = []
    for tag in SE_TAGS:
        posts.extend(stackexchange_client.fetch_posts(site="security", tagged=tag, pagesize=pagesize))
    return posts


def pull_hn(hits_per_page: int) -> list[Post]:
    posts: list[Post] = []
    for query in HN_QUERIES:
        posts.extend(hn_client.fetch_posts(query, hits_per_page=hits_per_page, fetch_comments=True))
    return posts


def to_jsonable(post: Post) -> dict:
    return {
        "id": post.id,
        "source": post.source,
        "subforum": post.subforum,
        "title": post.title,
        "body": post.body[:1500],
        "url": post.url,
        "permalink": post.permalink,
        "score": post.score,
        "num_replies": post.num_replies,
        "created_utc": post.created_utc,
        "top_replies": [r[:800] for r in post.top_replies],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["se", "hn", "both"], default="both")
    parser.add_argument("--se-pagesize", type=int, default=10)
    parser.add_argument("--hn-hits", type=int, default=6)
    args = parser.parse_args()

    posts: list[Post] = []
    if args.source in ("se", "both"):
        posts.extend(pull_se(args.se_pagesize))
    if args.source in ("hn", "both"):
        posts.extend(pull_hn(args.hn_hits))

    json.dump([to_jsonable(p) for p in posts], sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
