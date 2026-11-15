#!/usr/bin/env python3
"""Recall by meaning: facts ranked by how close they are to a question.

`gm-note.sh find --like "<question>"`. Ranking follows recall-proposal.md (§2, §8):

- **Who knows it is a hard filter** (`--held-by`, `--hidden`, `--secret`, `--truth`,
  `--category`, `--text`, `--since`/`--until`): those are recorded, not guessed.
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


def _number(fact: dict) -> int:
    digits = str(fact.get("id", ""))[1:]
    return int(digits) if digits.isdigit() else 0


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
           "secret": "someone knows it", "truth": "not {v}", "category": "not in {v}",
           "text": "lacks the words of --text", "since": "before {v}", "until": "after {v}"}


def _why_out(notes, fact: dict, hard: dict) -> str:
    """Which hard filter removed a fact, in a few words."""
    for name, value in hard.items():
        if value and fact["id"] not in {f["id"] for f in notes.find(**{name: value})}:
            shown = ", ".join(value) if isinstance(value, list) else value
            return REASONS[name].format(v=shown)
    return "filtered"


def find_like(notes, question: str, limit: int = 10, held_by=None, about=None, secret=False,
              hidden=False, truth=None, category=None, text=None, at=None, since=None,
              until=None, plot=None) -> dict:
    """{"facts": ranked facts (each with "score"), "method": "meaning" or "keywords",
    "near_misses": [(id, reason)], "not_embedded": n}. Raises ValueError for an
    unknown id, as find does."""
    hard = {"held_by": held_by, "secret": secret, "hidden": hidden, "truth": truth,
            "category": category, "text": text, "since": since, "until": until}
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
