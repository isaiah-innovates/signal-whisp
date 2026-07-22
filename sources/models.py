"""Shared post record — every source client normalizes into this shape.

See docs/architecture.md ("Shared post record") for the spec this implements.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Post:
    id: str
    source: str  # 'stackexchange' | 'hackernews' | 'reddit'
    subforum: str  # e.g. 'security.stackexchange.com', 'hackernews', 'r/msp'
    title: str
    body: str  # plain text, HTML stripped
    url: str
    permalink: str
    score: int
    num_replies: int
    created_utc: int
    top_replies: list[str] = field(default_factory=list)
