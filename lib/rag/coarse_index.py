#!/usr/bin/env python3
"""
Coarse chapter index — points INTO the retained book text, it is not the fidelity.

Its only job is to find the right CHAPTER, which the long-context reader then
loads in full (the piece-level search by meaning is vector_store.py). The scorer is
pluggable: a dependency-free keyword scorer by default, or "meaning" for semantic
recall's model (embedder.py), which falls back to keywords when it isn't installed. Query templates branch by
content type so a novel import stops dragging retrieval toward D&D stat-block
vocabulary.
"""

import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from book_bible import segment_into_chapters


def _template(query: str, content_type: str = "literary") -> str:
    """Branch the query by content type (literary prose vs game-module mechanics)."""
    if content_type == "game-module":
        return f"{query} stat block rules mechanics encounter"
    return f"{query} scene character atmosphere setting"


def _keyword_score(query: str, text: str) -> float:
    q = set(re.findall(r"\w+", query.lower()))
    t = set(re.findall(r"\w+", text.lower()))
    if not q:
        return 0.0
    return len(q & t)


class CoarseIndex:
    """A chapter-granularity index that returns POINTERS, never chunk blobs."""

    def __init__(self, embedder: str = "keyword"):
        self.embedder = embedder  # pluggable: "keyword" (default) or "meaning"
        self.chapters: list[dict[str, Any]] = []

    def build(self, text: str) -> int:
        self.chapters = segment_into_chapters(text)
        return len(self.chapters)

    def _score(self, query: str, text: str) -> float:
        if self.embedder == "keyword":
            return _keyword_score(query, text)
        from embedder import get_embedder
        emb = get_embedder()
        if emb is None:                              # semantic recall not installed
            return _keyword_score(query, text)
        return float(emb.query(query) @ emb.document(text))

    def query(self, query: str, content_type: str = "literary", top_k: int = 3) -> list[dict[str, Any]]:
        """Return ranked CHAPTER POINTERS {index, title, score} — not the text."""
        templated = _template(query, content_type)
        scored = [(self._score(templated, c["text"]), c) for c in self.chapters]
        scored.sort(key=lambda t: t[0], reverse=True)
        return [{"index": c["index"], "title": c["title"], "score": s}
                for s, c in scored[:top_k] if s > 0]

    def load_chapter(self, index: int) -> dict[str, Any]:
        """Resolve a pointer to its full chapter text (what the long-context reader loads)."""
        for c in self.chapters:
            if c["index"] == index:
                return c
        return {}
