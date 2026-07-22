"""Shared helpers for source clients."""

from __future__ import annotations

import re
from html import unescape
from html.parser import HTMLParser


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []

    def handle_data(self, data: str) -> None:
        self._chunks.append(data)

    def text(self) -> str:
        return "".join(self._chunks)


def strip_html(raw: str | None) -> str:
    """Strip HTML tags and collapse whitespace, returning plain text."""
    if not raw:
        return ""
    parser = _TextExtractor()
    parser.feed(raw)
    text = unescape(parser.text())
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", text)).strip()
