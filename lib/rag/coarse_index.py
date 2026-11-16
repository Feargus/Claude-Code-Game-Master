#!/usr/bin/env python3
"""
Coarse chapter index — points INTO the retained book text, it is not the fidelity.

Its only job is to find the right CHAPTER, which the long-context reader then
loads in full. By meaning when it can (2026-11-16): the book's indexed pieces
(vector_store.py) closest to the question vote for the chapters they come from, so
no extra index is needed and a chapter longer than the model reads is no problem.
By keywords (word overlap, no model) when the campaign's book has no index or
semantic recall isn't installed. Query templates branch by
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

    PIECES = 12                 # the closest pieces that vote for their chapters

    def __init__(self, embedder: str = "keyword", store=None):
        self.embedder = embedder  # "keyword" (default) or "meaning"
        self.store = store        # the book's pieces and vectors, for "meaning"
        self.chapters: list[dict[str, Any]] = []
        self.method = "keyword"   # what the last query ranked by

    def build(self, text: str) -> int:
        self.chapters = segment_into_chapters(text)
        return len(self.chapters)

    def _score(self, query: str, text: str) -> float:
        return _keyword_score(query, text)

    def _query_meaning(self, query: str, top_k: int) -> list[dict[str, Any]]:
        """Chapters by the pieces closest to the question: each of the PIECES best
        adds its similarity to the chapter it lies in. [] when nothing maps."""
        from embedder import get_embedder
        embedder = get_embedder()
        if embedder is None:
            return []
        found = self.store.query_by_text(query, embedder, n_results=self.PIECES)
        votes: dict[int, float] = {}
        for text, distance in zip(found["documents"], found["distances"], strict=True):
            head = text.strip()[:120]
            for c in self.chapters:
                if head and head in c["text"]:
                    votes[c["index"]] = votes.get(c["index"], 0.0) + (1.0 - distance)
                    break
        ranked = sorted(votes.items(), key=lambda kv: -kv[1])[:top_k]
        by_index = {c["index"]: c for c in self.chapters}
        return [{"index": i, "title": by_index[i]["title"], "score": round(s, 3)} for i, s in ranked]

    def query(self, query: str, content_type: str = "literary", top_k: int = 3) -> list[dict[str, Any]]:
        """Return ranked CHAPTER POINTERS {index, title, score} — not the text."""
        if self.embedder == "meaning" and self.store is not None:
            pointers = self._query_meaning(query, top_k)
            if pointers:
                self.method = "meaning"
                return pointers
        self.method = "keyword"
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
