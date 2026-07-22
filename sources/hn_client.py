"""Hacker News (Algolia Search API) client — secondary live source.

Spec: docs/data-sources.md ("Hacker News (Algolia Search API) — SECONDARY live source").
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import requests

from sources.models import Post
from sources.util import strip_html

BASE_URL = "https://hn.algolia.com/api/v1"


def search(query: str, tags: str = "story", hits_per_page: int = 20, by_date: bool = False) -> list[dict]:
    """Search HN. by_date=False uses relevance-ranked /search (good for one-off
    discovery); by_date=True uses /search_by_date (good for daily incremental pulls).
    """
    endpoint = "/search_by_date" if by_date else "/search"
    params = {"query": query, "tags": tags, "hitsPerPage": hits_per_page}
    resp = requests.get(f"{BASE_URL}{endpoint}", params=params, timeout=30)
    resp.raise_for_status()
    return resp.json().get("hits", [])


def fetch_item(item_id: int) -> dict:
    """Full item detail including nested comment tree — one call per story."""
    resp = requests.get(f"{BASE_URL}/items/{item_id}", timeout=30)
    resp.raise_for_status()
    return resp.json()


def _top_level_comment_texts(item: dict, top_n: int) -> list[str]:
    children = item.get("children") or []
    texts = []
    for child in children:
        text = child.get("text")
        if text:
            texts.append(strip_html(text))
        if len(texts) >= top_n:
            break
    return texts


def fetch_posts(
    query: str,
    tags: str = "story",
    hits_per_page: int = 20,
    by_date: bool = False,
    top_n_replies: int = 3,
    fetch_comments: bool = True,
) -> list[Post]:
    """Search HN and normalize hits into shared Post records.

    fetch_comments makes one extra request per hit to pull top-level comments
    as corroboration context — disable for high-volume pulls to limit call count.
    """
    hits = search(query, tags=tags, hits_per_page=hits_per_page, by_date=by_date)

    posts: list[Post] = []
    for hit in hits:
        object_id = hit.get("objectID")
        title = hit.get("title") or hit.get("story_title") or ""
        body = hit.get("story_text") or hit.get("comment_text") or ""
        top_replies: list[str] = []
        if fetch_comments and object_id:
            item = fetch_item(int(object_id))
            top_replies = _top_level_comment_texts(item, top_n_replies)

        posts.append(
            Post(
                id=str(object_id),
                source="hackernews",
                subforum="hackernews",
                title=strip_html(title),
                body=strip_html(body),
                url=hit.get("url") or f"https://news.ycombinator.com/item?id={object_id}",
                permalink=f"https://news.ycombinator.com/item?id={object_id}",
                score=hit.get("points", 0) or 0,
                num_replies=hit.get("num_comments", 0) or 0,
                created_utc=hit.get("created_at_i", 0) or 0,
                top_replies=top_replies,
            )
        )
    return posts


def fetch_post_by_id(item_id: int, top_n_replies: int = 3) -> Post:
    """Fetch a single HN item and normalize it into a shared Post record."""
    item = fetch_item(item_id)
    top_replies = _top_level_comment_texts(item, top_n_replies)
    return Post(
        id=str(item_id),
        source="hackernews",
        subforum="hackernews",
        title=strip_html(item.get("title") or ""),
        body=strip_html(item.get("text") or ""),
        url=item.get("url") or f"https://news.ycombinator.com/item?id={item_id}",
        permalink=f"https://news.ycombinator.com/item?id={item_id}",
        score=item.get("points", 0) or 0,
        num_replies=len(item.get("children") or []),
        created_utc=item.get("created_at_i", 0) or 0,
        top_replies=top_replies,
    )


def fetch_post(permalink: str, top_n_replies: int = 3) -> Post:
    """Re-fetch a single post by its permalink (used to re-hydrate eval rows,
    which store only the permalink and labels, not the full post content)."""
    parsed = urlparse(permalink)
    item_id = int(parse_qs(parsed.query)["id"][0])
    return fetch_post_by_id(item_id, top_n_replies=top_n_replies)
