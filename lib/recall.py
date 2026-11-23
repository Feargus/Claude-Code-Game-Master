#!/usr/bin/env python3
"""Recall by meaning: facts ranked by how close they are to a question.

`gm-note.sh find --like "<question>"` (docs/modules/campaign-memory.md). The ranking:

- **Who knows it is a hard filter** (`--held-by`, `--hidden`, `--secret`, `--truth`,
  `--text`, `--since`/`--until`): those are recorded, not guessed.
- **What comes from matching words is a bonus, never a filter.** `about` and `at`
  are found by names in the text, and plots are linked by hand, so all three can
  be missing ("the clown came back" isn't linked to Pagliacci). With `--like`,
  `--about`, `--at` and `--plot` raise a fact's score instead of excluding it.
- **Near-misses are shown:** facts that would rank among the shown ones but a hard
  filter removed are named by id, with the reason, so a gap in the data shows.

The score: similarity to the question (−1 … 1), plus 0.10 when the fact is about
someone or something given with `--about`, 0.05 when it happened at `--at`, 0.05
when it belongs to `--plot`, and up to 0.05 for recency (the newest fact, fading
to nothing over the last 50). The numbers are first guesses, to tune in play.

Without semantic recall installed (embedder.py), the same filters and bonuses
apply to a keyword score (BM25), and the output says so.
"""

import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

ABOUT_BONUS, AT_BONUS, PLOT_BONUS, RECENCY_BONUS, RECENCY_SPAN = 0.10, 0.05, 0.05, 0.05, 50
EMBED_AT_ONCE = 10      # facts not embedded yet that a query embeds itself; the rest count as average
NEAR_MISSES = 3


import facts as fact_file  # noqa: E402 (after the path line above, like every lib import)

_number = fact_file.number


# ---------- keyword score (the fallback) ----------

STOP_WORDS = ("a an the and or of to in on at for with by from is are was were be been it its his "
              "her he she they them their this that what who whom which where when how has have "
              "had do does did not no as into than then there here")
STOP = set(STOP_WORDS.split())


def _words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9']+", str(text).lower()) if w not in STOP]


def bm25(question: str, texts: list[str], k1: float = 1.5, b: float = 0.75) -> list[float]:
    docs = [_words(t) for t in texts]
    n, avg = len(docs), sum(map(len, docs)) / max(1, len(docs))
    df = {}
    for d in docs:
        for w in set(d):
            df[w] = df.get(w, 0) + 1
    out = []
    for d in docs:
        s = 0.0
        for w in _words(question):
            f = d.count(w)
            if f:
                idf = math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5))
                s += idf * f * (k1 + 1) / (f + k1 * (1 - b + b * len(d) / max(avg, 1)))
        out.append(s)
    top = max(out, default=0) or 1
    return [s / top for s in out]           # 0 … 1, so the bonuses weigh as with similarity


# ---------- similarity by meaning ----------

def similarities(campaign_dir, question: str, facts: list[dict]):
    """({fact id: similarity}, embedder name, how many weren't embedded yet), or
    (None, None, 0) when semantic recall isn't installed."""
    from embedder import get_embedder
    from embedding_store import EmbeddingStore
    embedder = get_embedder()
    if embedder is None:
        return None, None, 0
    stored = EmbeddingStore(campaign_dir).vectors(embedder.name)
    q = embedder.query(question)
    sims, missing = {}, []
    for f in facts:
        v = stored.get(f"fact:{f['id']}")
        if v is None:
            missing.append(f)
        else:
            sims[f["id"]] = float(v @ q)
    for f in missing[:EMBED_AT_ONCE]:          # just recorded: embed it here (not saved:
        sims[f["id"]] = float(embedder.document(f["fact"]) @ q)    # the background job does)
    rest = missing[EMBED_AT_ONCE:]
    if rest:
        average = sum(sims.values()) / len(sims) if sims else 0.0
        for f in rest:
            sims[f["id"]] = average
    return sims, embedder.name, len(rest)


# ---------- the ranking ----------

def _bonus(fact: dict, abouts, place, plot_key, newest: int) -> float:
    bonus = 0.0
    if abouts and set(abouts) & set(fact.get("about") or []):
        bonus += ABOUT_BONUS
    if place and fact.get("at") == place:
        bonus += AT_BONUS
    if plot_key and plot_key in (fact.get("plots") or []):
        bonus += PLOT_BONUS
    age = newest - _number(fact)
    if 0 <= age < RECENCY_SPAN:
        bonus += RECENCY_BONUS * (1 - age / RECENCY_SPAN)
    return bonus


REASONS = {"held_by": "not held by {v}", "hidden": "the character knows it",
           "secret": "someone knows it", "truth": "not {v}",
           "text": "lacks the words of --text", "since": "before {v}", "until": "after {v}"}


def _why_out(notes, fact: dict, hard: dict) -> str:
    """Which hard filter removed a fact, in a few words."""
    for name, value in hard.items():
        if value and fact["id"] not in {f["id"] for f in notes.find(**{name: value})}:
            shown = ", ".join(value) if isinstance(value, list) else value
            return REASONS[name].format(v=shown)
    return "filtered"


def find_like(notes, question: str, limit: int = 10, held_by=None, about=None, secret=False,
              hidden=False, truth=None, text=None, at=None, since=None,
              until=None, plot=None) -> dict:
    """{"facts": ranked facts (each with "score"), "method": "meaning" or "keywords",
    "near_misses": [(id, reason)], "not_embedded": n}. Raises ValueError for an
    unknown id, as find does."""
    hard = {"held_by": held_by, "secret": secret, "hidden": hidden, "truth": truth,
            "text": text, "since": since, "until": until}
    allowed = notes.find(**hard)              # resolves and checks the hard filters
    # The soft ones, resolved the same way find does (an unknown name is still an error).
    from world_ids import WorldIds
    ids = WorldIds(notes.json_ops)
    abouts, errors = ids.resolve_all(about)
    place = None
    if at:
        place, error = ids.resolve_as(at, ("location",))
        errors += [error] if error else []
    plot_key = ""
    if plot:
        from plot_manager import resolve_plots
        keys, more = resolve_plots(notes.json_ops, [plot])
        errors += more
        plot_key = keys[0] if keys else ""
    if errors:
        raise ValueError("; ".join(errors))

    everything = notes.find()
    newest = max((_number(f) for f in everything), default=0)
    sims, method, not_embedded = similarities(notes.campaign_dir, question, everything)
    if sims is None:
        scores = dict(zip((f["id"] for f in everything),
                          bm25(question, [f.get("fact", "") for f in everything]), strict=True))
        method = "keywords"
    else:
        scores, method = sims, "meaning"
    ranked_all = sorted(everything, key=lambda f: -(scores.get(f["id"], 0.0) + _bonus(
        f, abouts, place, plot_key, newest)))
    allowed_ids = {f["id"] for f in allowed}
    by_id = {f["id"]: f for f in allowed}      # find marks public matches; keep its copies
    shown = [dict(by_id[f["id"]], score=round(scores.get(f["id"], 0.0)
                                               + _bonus(f, abouts, place, plot_key, newest), 3))
             for f in ranked_all if f["id"] in allowed_ids][:limit or None]
    cutoff = shown[-1]["score"] if shown else float("inf")
    near = []
    if any(hard.values()):
        for f in ranked_all:
            score = scores.get(f["id"], 0.0) + _bonus(f, abouts, place, plot_key, newest)
            if score < cutoff or len(near) >= NEAR_MISSES:
                break
            if f["id"] not in allowed_ids:
                near.append((f["id"], _why_out(notes, f, hard)))
    return {"facts": shown, "method": method, "near_misses": near, "not_embedded": not_embedded,
            "total": len(allowed)}


def print_found(result: dict, fact_line) -> None:
    how = ("ranked by meaning" if result["method"] == "meaning" else
           "ranked by keywords (semantic recall is off: bash tools/gm-recall.sh status)")
    print(f"Facts {how}, best first:")
    for f in result["facts"]:
        print(fact_line(f))
    if not result["facts"]:
        print("No facts match.")
    more = result["total"] - len(result["facts"])
    if more > 0:
        print(f"+{more} more, ranked lower (--limit 0 for all)")
    if result["near_misses"]:
        print("Close by meaning, but filtered out: " + ", ".join(
            f"{fid} ({why})" for fid, why in result["near_misses"]))
    if result["not_embedded"]:
        print(f"({result['not_embedded']} facts are not embedded yet and count as average: "
              f"bash tools/gm-recall.sh embed)")


# ---------- a new plot: which recorded facts look part of it ----------

def suggest_for_plot(notes, plot_key: str, limit: int = 5) -> dict:
    """The facts not in the plot that are closest to what it is about, best first,
    for the GM to link. Facts about the people and
    places it involves get the --about bonus. {"facts": [...], "method": ...}."""
    plot = (notes.json_ops.load_json("plots.json") or {}).get(plot_key) or {}
    from embedding_store import plot_text
    text = plot_text(plot_key, plot)
    facts = [f for f in notes.find() if not f.get("attitude")
             and plot_key not in (f.get("plots") or [])]
    if not facts:
        return {"facts": [], "method": "meaning"}
    sims, method, _ = similarities(notes.campaign_dir, text, facts)
    if sims is None:
        scores = dict(zip((f["id"] for f in facts), bm25(text, [f["fact"] for f in facts]),
                          strict=True))
        facts = [f for f in facts if scores[f["id"]] > 0]     # keywords: only what shares a word
        method = "keywords"
    else:
        scores, method = sims, "meaning"
    involved = set(plot.get("involves") or [])
    def score(f):
        return scores.get(f["id"], 0.0) + (ABOUT_BONUS if involved & set(f.get("about") or []) else 0)
    return {"facts": sorted(facts, key=score, reverse=True)[:limit], "method": method}


# ---------- a new person or place: someone like this exists already ----------

SAME_MEANING = 0.70     # measured 2026-11-15: a person re-described scored 0.63-0.74
                        # against the original; different people at most 0.65, typically 0.37.
                        # Raised from 0.60 after the carnaval playtest (2026-11-20), where both
                        # refusals were wrong (0.62, 0.67); watch for doubles that now get through.


def close_in_meaning(json_ops, kind: str, text: str):
    """(name, similarity) of the existing person or place (`kind` "npc" or
    "location") closest in meaning to `text`, when it reaches SAME_MEANING; else
    None. Only once play has begun (the opening has run): building a world makes
    many records at once, and each check loads the model (about 7 s)."""
    if not (json_ops.load_json("campaign-overview.json") or {}).get("opened"):
        return None
    from embedder import get_embedder
    from embedding_store import EmbeddingStore, location_text, npc_text
    embedder = get_embedder()
    if embedder is None:
        return None
    records = json_ops.load_json("npcs.json" if kind == "npc" else "locations.json") or {}
    if not records:
        return None
    stored = EmbeddingStore(json_ops.world_state_dir).vectors(embedder.name)
    new = embedder.document(text)
    best, inline = None, 0
    for name, record in records.items():
        if not isinstance(record, dict):
            continue
        v = stored.get(f"{kind}:{name}")
        if v is None and inline < EMBED_AT_ONCE:
            inline += 1
            v = embedder.document(npc_text(name, record) if kind == "npc" else
                                  location_text(name, record))
        if v is not None:
            sim = float(v @ new)
            if best is None or sim > best[1]:
                best = (name, sim)
    return best if best and best[1] >= SAME_MEANING else None


def meaning_refusal(kind: str, new: str, hit) -> str:
    what, tool = ("person", "gm-npc.sh show") if kind == "npc" else ("place", "gm-location.sh get")
    alias = "gm-npc.sh alias" if kind == "npc" else "gm-location.sh alias"
    who = "who" if kind == "npc" else "which"
    return (f"'{new}' reads like {hit[0]}, {who} exists already (closeness {hit[1]:.2f}). The same "
            f"{what} under two names splits what is known about them, so this is refused: look "
            f"at bash tools/{tool} \"{hit[0]}\". If it is the same {what}, give it the new name "
            f"as an alias ({alias}). If it really is another {what}, add --another.")


# ---------- the scene: what the cards and the brief rank by ----------

class SceneRanker:
    """Ranks facts by how well they fit the scene, with no model loaded: the query
    is the average of vectors that exist already: the
    place's description, the last 3 facts recorded here, and the sentence of each
    open plot that involves the place or someone in the scene. The score adds the
    same bonuses as find --like, with "here" meaning the place and the people in
    the scene. Without vectors (semantic recall off, or not embedded yet), the
    bonuses and recency alone decide: the place's and the people's own facts first,
    newest first among them."""

    def __init__(self, json_ops, location: str, present=()):
        from embedder import get_embedder
        from embedding_store import EmbeddingStore
        embedder = get_embedder()
        self.vectors = (EmbeddingStore(json_ops.world_state_dir).vectors(embedder.name)
                        if embedder else {})
        everything = [f for f in fact_file.load(json_ops) if f.get("id")]
        self.newest = max((_number(f) for f in everything), default=0)
        self.place = f"location:{location}" if location else ""
        self.here = {self.place} | {f"npc:{n}" for n in present} - {""}
        plots = json_ops.load_json("plots.json") or {}
        self.plots_here = {k for k, p in plots.items() if isinstance(p, dict)
                           and p.get("status", "open") == "open"
                           and self.here & set(p.get("involves") or [])}
        parts = [self.vectors.get(self.place)]
        recent_here = sorted((f for f in everything if self.place and f.get("at") == self.place),
                             key=_number, reverse=True)[:3]
        parts += [self.vectors.get(f"fact:{f['id']}") for f in recent_here]
        parts += [self.vectors.get(f"plot:{k}") for k in sorted(self.plots_here)]
        parts = [v for v in parts if v is not None]
        self.query = None
        if parts:
            import numpy as np
            q = np.mean(parts, axis=0)
            self.query = q / (np.linalg.norm(q) or 1)
        self._sims = None

    def _similarity(self, fact: dict) -> float:
        if self.query is None:
            return 0.0
        if self._sims is None:
            self._sims = {k: float(v @ self.query) for k, v in self.vectors.items()
                          if k.startswith("fact:")}
            self._average = sum(self._sims.values()) / len(self._sims) if self._sims else 0.0
        return self._sims.get(f"fact:{fact.get('id')}", self._average)

    def score(self, fact: dict) -> float:
        bonus = 0.0
        if self.here & set(fact.get("about") or []):
            bonus += ABOUT_BONUS
        if self.place and fact.get("at") == self.place:
            bonus += AT_BONUS
        if self.plots_here & set(fact.get("plots") or []):
            bonus += PLOT_BONUS
        age = self.newest - _number(fact)
        if 0 <= age < RECENCY_SPAN:
            bonus += RECENCY_BONUS * (1 - age / RECENCY_SPAN)
        return self._similarity(fact) + bonus

    def rank(self, facts: list[dict]) -> list[dict]:
        """Best fit first; newest first on a tie."""
        return sorted(facts, key=lambda f: (-self.score(f), -_number(f)))

    @property
    def by_meaning(self) -> bool:
        return self.query is not None
