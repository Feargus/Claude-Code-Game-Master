#!/usr/bin/env python3
"""
Long-term campaign memory: recall over the campaign's own history.

Recalls from the plots (what each is about, where it stands, what came of it)
and the facts, read as they are now. A provenance dimension separates
book-canon from our-story. Semantic recall uses embeddings when the RAG deps
are installed (`refresh`); otherwise keyword overlap.
"""

import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from entity_manager import EntityManager
from note_manager import fact_text

_CANON_CATEGORIES = {"plot_world", "world_building"}
# Keyword recall breaks ties by tier: plots (they sum up their facts), then facts.
_TIE_ORDER = {"plot": 0, "archive": 1}


class CampaignMemory(EntityManager):
    def __init__(self, world_state_dir: str = None):
        super().__init__(world_state_dir)
        self.memory_file = "campaign-memory.json"

    def gather(self) -> list[dict[str, Any]]:
        """Everything recall searches, read as it is now: each plot (what it is
        about, where it stands, what came of it) and each fact."""
        entries: list[dict[str, Any]] = []

        plots = self.json_ops.load_json("plots.json") or {}
        for key, p in plots.items() if isinstance(plots, dict) else []:
            if not isinstance(p, dict):
                continue
            text = " ".join(str(p.get(f) or "").strip()
                            for f in ("description", "stands", "summary") if p.get(f))
            if text:
                entries.append({"text": f"{key}: {text}", "provenance": "our-story",
                                "source": f"plot:{key}", "tier": "plot"})

        facts = self.json_ops.load_json("facts.json") or {}
        if isinstance(facts, dict):
            for cat, items in facts.items():
                if not isinstance(items, list):
                    continue
                prov = "book-canon" if cat in _CANON_CATEGORIES else "our-story"
                for it in items:
                    t = fact_text(it) if isinstance(it, dict) and it.get("fact") else (
                        "" if isinstance(it, dict) else str(it))
                    if t:
                        entries.append({"text": t, "provenance": prov,
                                        "source": f"facts:{cat}", "tier": "archive"})
        return entries

    # ---- recall ----

    def entries(self) -> list[dict[str, Any]]:
        """Everything recall searches (gather), read fresh every time, so a fact
        is recallable the moment it is recorded; nothing is kept in a copy that
        could go stale."""
        return self.gather()

    @staticmethod
    def _hash(entries: list[dict[str, Any]]) -> str:
        import hashlib
        return hashlib.md5("\x1f".join(e["text"] for e in entries).encode("utf-8")).hexdigest()

    def refresh(self) -> int:
        """Recompute the embeddings for semantic recall, when the RAG deps are
        installed and the entries changed since the last time. Without the deps
        there is nothing to keep: keyword recall reads the entries directly.
        campaign-memory.json holds the embeddings and the hash of the texts they
        belong to. Returns the number of entries."""
        entries = self.entries()
        data = self.json_ops.load_json(self.memory_file) or {}
        had = dict(data)
        data.pop("entries", None)          # the copy older versions kept
        data.pop("arcs", None)             # folded into plots (2026-11-14)
        content_hash = self._hash(entries)
        if data.get("entries_hash") != content_hash or not data.get("embeddings"):
            vectors = self._embed_batch([e["text"] for e in entries])  # None when deps missing
            if vectors:
                data["entries_hash"], data["embeddings"] = content_hash, vectors
            else:
                data.pop("entries_hash", None)
                data.pop("embeddings", None)
        if not any(data.values()):          # nothing to keep: no embeddings
            (self.campaign_dir / self.memory_file).unlink(missing_ok=True)
        elif data != had:
            self.json_ops.save_json(self.memory_file, data)
        return len(entries)

    @staticmethod
    def _embed_batch(texts):
        """Embed texts via LocalEmbedder; None when RAG deps are missing."""
        if not texts:
            return []
        try:
            from rag.embedder import LocalEmbedder
            vecs = LocalEmbedder().embed_batch(texts)
            return [[round(float(x), 4) for x in v] for v in vecs]
        except ImportError:
            return None

    def recall(self, query: str, top_k: int = 5, provenance: str = None) -> list[dict[str, Any]]:
        """Recall over the campaign's history: cosine over stored embeddings
        when they belong to the entries as they are now, keyword overlap
        otherwise (no RAG deps, or facts recorded since the last refresh)."""
        entries = self.entries()
        data = self.json_ops.load_json(self.memory_file) or {}
        vectors = data.get("embeddings")

        if vectors and len(vectors) == len(entries) and data.get("entries_hash") == self._hash(entries):
            hits = self._recall_semantic(query, entries, vectors, top_k, provenance)
            if hits is not None:
                return hits
        return self._recall_keyword(query, entries, top_k, provenance)

    @staticmethod
    def _recall_semantic(query, entries, vectors, top_k, provenance):
        """Cosine top-k; None when deps are missing (caller falls back)."""
        try:
            from rag.embedder import LocalEmbedder
        except ImportError:
            return None
        q = LocalEmbedder().embed(query)
        import math
        qn = math.sqrt(sum(x * x for x in q)) or 1.0
        scored = []
        for e, v in zip(entries, vectors, strict=True):
            if provenance and e.get("provenance") != provenance:
                continue
            dot = sum(a * b for a, b in zip(q, v, strict=False))
            vn = math.sqrt(sum(b * b for b in v)) or 1.0
            scored.append((dot / (qn * vn), e))
        scored.sort(key=lambda t: t[0], reverse=True)
        return [e for _, e in scored[:top_k]]

    @staticmethod
    def _recall_keyword(query, entries, top_k, provenance):
        """Entries sharing the most words with the query. On a tie, plots come
        first (they sum up their facts), then facts; within each, the order
        gathered (oldest first)."""
        if provenance:
            entries = [e for e in entries if e.get("provenance") == provenance]
        q = set(re.findall(r"\w+", query.lower()))
        if not q:
            return []
        scored = []
        for i, e in enumerate(entries):
            tw = set(re.findall(r"\w+", e["text"].lower()))
            s = len(q & tw)
            if s > 0:
                scored.append((-s, _TIE_ORDER.get(e.get("tier"), len(_TIE_ORDER)), i, e))
        scored.sort(key=lambda t: t[:3])
        return [t[3] for t in scored[:top_k]]


def main():
    import argparse
    import json

    from cli_output import emit, strip_json_flag, wants_json

    parser = argparse.ArgumentParser(description="Campaign memory")
    sub = parser.add_subparsers(dest="action")
    r = sub.add_parser("recall")
    r.add_argument("query", nargs="+")
    r.add_argument("--top-k", type=int, default=5)
    r.add_argument("--provenance", choices=["our-story", "book-canon"])
    sub.add_parser("refresh")

    json_mode = wants_json()
    args = parser.parse_args(strip_json_flag(sys.argv[1:]))
    if not args.action:
        parser.print_help()
        sys.exit(1)

    m = CampaignMemory()
    if args.action == "recall":
        out = m.recall(" ".join(args.query), top_k=args.top_k,
                       provenance=getattr(args, "provenance", None))
    elif args.action == "refresh":
        out = {"indexed": m.refresh()}
    else:
        parser.print_help()
        sys.exit(1)

    if json_mode:
        emit(out, json_mode=True)
    else:
        print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
