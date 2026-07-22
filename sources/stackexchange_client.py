"""Stack Exchange API client — primary live source.

Spec: docs/data-sources.md ("Stack Exchange API — PRIMARY live source").
"""

from __future__ import annotations

import os
import time
from urllib.parse import urlparse

import requests

from sources.models import Post
from sources.util import strip_html

BASE_URL = "https://api.stackexchange.com/2.3"

_SITE_DOMAINS = {
    "security": "security.stackexchange.com",
    "serverfault": "serverfault.com",
    "superuser": "superuser.com",
}
_DOMAIN_SITES = {domain: site for site, domain in _SITE_DOMAINS.items()}


def _get(path: str, params: dict) -> dict:
    key = os.environ.get("STACKEXCHANGE_KEY")
    if key:
        params = {**params, "key": key}
    resp = requests.get(f"{BASE_URL}{path}", params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    backoff = data.get("backoff")
    if backoff:
        time.sleep(backoff)
    return data


def fetch_questions(
    site: str = "security",
    tagged: str | None = None,
    sort: str = "activity",
    order: str = "desc",
    pagesize: int = 30,
    fromdate: int | None = None,
) -> list[dict]:
    """Raw /questions call. tagged is a semicolon-joined tag string, e.g. 'phishing'."""
    params = {
        "site": site,
        "sort": sort,
        "order": order,
        "pagesize": pagesize,
        "filter": "withbody",
    }
    if tagged:
        params["tagged"] = tagged
    if fromdate:
        params["fromdate"] = fromdate
    data = _get("/questions", params)
    return data.get("items", [])


def fetch_answers(question_ids: list[int], site: str = "security") -> dict[int, list[dict]]:
    """Batch-fetch answers for up to 100 question ids at a time.

    Returns a map of question_id -> list of raw answer dicts, sorted by votes desc.
    """
    answers_by_question: dict[int, list[dict]] = {}
    for i in range(0, len(question_ids), 100):
        batch = question_ids[i : i + 100]
        ids_param = ";".join(str(q) for q in batch)
        data = _get(
            f"/questions/{ids_param}/answers",
            {
                "site": site,
                "filter": "withbody",
                "order": "desc",
                "sort": "votes",
            },
        )
        for item in data.get("items", []):
            answers_by_question.setdefault(item["question_id"], []).append(item)
    return answers_by_question


def fetch_posts(
    site: str = "security",
    tagged: str | None = None,
    pagesize: int = 30,
    fromdate: int | None = None,
    top_n_replies: int = 3,
) -> list[Post]:
    """Fetch questions plus their top answers, normalized into shared Post records."""
    questions = fetch_questions(site=site, tagged=tagged, pagesize=pagesize, fromdate=fromdate)
    if not questions:
        return []

    answers_by_question = fetch_answers([q["question_id"] for q in questions], site=site)

    posts: list[Post] = []
    for q in questions:
        qid = q["question_id"]
        answers = answers_by_question.get(qid, [])
        top_replies = [strip_html(a["body"]) for a in answers[:top_n_replies]]
        posts.append(
            Post(
                id=str(qid),
                source="stackexchange",
                subforum=_SITE_DOMAINS.get(site, site),
                title=strip_html(q.get("title", "")),
                body=strip_html(q.get("body", "")),
                url=q.get("link", ""),
                permalink=q.get("link", ""),
                score=q.get("score", 0),
                num_replies=q.get("answer_count", 0),
                created_utc=q.get("creation_date", 0),
                top_replies=top_replies,
            )
        )
    return posts


def fetch_post(permalink: str, top_n_replies: int = 3) -> Post:
    """Re-fetch a single post by its permalink (used to re-hydrate eval rows,
    which store only the permalink and labels, not the full post content)."""
    parsed = urlparse(permalink)
    site = _DOMAIN_SITES[parsed.netloc]
    segments = [s for s in parsed.path.split("/") if s]
    question_id = int(segments[1])  # segments[0] == "questions"

    data = _get(f"/questions/{question_id}", {"site": site, "filter": "withbody"})
    items = data.get("items", [])
    if not items:
        raise ValueError(f"No question found for {permalink}")
    q = items[0]

    answers = fetch_answers([question_id], site=site).get(question_id, [])
    top_replies = [strip_html(a["body"]) for a in answers[:top_n_replies]]

    return Post(
        id=str(question_id),
        source="stackexchange",
        subforum=_SITE_DOMAINS.get(site, site),
        title=strip_html(q.get("title", "")),
        body=strip_html(q.get("body", "")),
        url=q.get("link", ""),
        permalink=q.get("link", ""),
        score=q.get("score", 0),
        num_replies=q.get("answer_count", 0),
        created_utc=q.get("creation_date", 0),
        top_replies=top_replies,
    )
