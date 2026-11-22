#!/usr/bin/env python3
"""Notes from the background job about the facts it just embedded, printed by the
GM's next command (recall-proposal.md, step f, decision 5).

After embedding a new fact, the job compares it with what it might belong to:

- **a plot**, when the fact is in none: the open plot it is closest to, if that
  plot is clearly the best (PLOT_NOTE, and PLOT_MARGIN ahead of the next);
- **a person it reads like it is about but isn't linked to** (a missed name
  check: "the clown came back", Pagliacci): ABOUT_NOTE or more, and closer than
  the character and everyone it is linked to already, so a person whose record
  is about the character (a copy of them) isn't suggested for every fact;
- **a consequence waiting on an event** it may fulfil: the closest, CONSEQUENCE_NOTE
  or more.

The thresholds come from a measurement on three campaigns (2026-11-15) and are
first guesses, to tune in play. The notes are kept in `embeddings.notes.json`
(derived, not in git) and printed once, at the start of the next command that
needs an active campaign (tools/common.sh), each checked again first: a note the
GM has acted on in the meantime is dropped.

    recall_notes.py print <campaign folder>
"""

import contextlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

NOTES = "embeddings.notes.json"
PLOT_NOTE, PLOT_MARGIN = 0.45, 0.05
ABOUT_NOTE = 0.55
CONSEQUENCE_NOTE = 0.65         # 0.50 until 2026-11-22: all nine notes in the Long Hull playtest (0.51–0.62) were wrong


def _load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    except ValueError:
        return None


def _facts(campaign_dir: Path) -> dict:
    data = _load(campaign_dir / "facts.json")
    return {f["id"]: f for f in (data if isinstance(data, list) else [])
            if isinstance(f, dict) and f.get("id")}


def _waiting(campaign_dir: Path) -> list[dict]:
    store = _load(campaign_dir / "consequences.json") or {}
    active = store.get("active", []) if isinstance(store, dict) else []
    return [c for c in active if isinstance(c, dict) and any(
        isinstance(t, dict) and t.get("type") == "on_event" for t in c.get("triggers") or [])]


def make_notes(campaign_dir, fact_ids, embedder, vectors: dict) -> list[dict]:
    """The notes for the facts just embedded. `vectors`: the store's {key: vector}."""
    campaign_dir = Path(campaign_dir)
    facts = _facts(campaign_dir)
    plots = {k: p for k, p in (_load(campaign_dir / "plots.json") or {}).items()
             if isinstance(p, dict) and p.get("status", "open") == "open"}
    waiting = _waiting(campaign_dir)
    consequence_vectors = {}
    if waiting:
        for c in waiting:
            when = " or ".join(str(t.get("match")) for t in c.get("triggers") or []
                               if isinstance(t, dict) and t.get("type") == "on_event")
            consequence_vectors[c["id"]] = embedder.document(f"{c.get('consequence', '')} When: {when}")
    people = {k: v for k, v in vectors.items() if k.startswith("npc:")}
    player = vectors.get("player")
    notes = []
    for fid in fact_ids:
        fact, v = facts.get(fid), vectors.get(f"fact:{fid}")
        if fact is None or v is None or fact.get("attitude"):
            continue
        if not fact.get("plots"):
            ranked = sorted(((float(v @ vectors[f"plot:{k}"]), k) for k in plots
                             if f"plot:{k}" in vectors), reverse=True)
            if ranked and ranked[0][0] >= PLOT_NOTE and (
                    len(ranked) == 1 or ranked[0][0] - ranked[1][0] >= PLOT_MARGIN):
                notes.append({"fact": fid, "kind": "plot", "target": ranked[0][1],
                              "score": round(ranked[0][0], 2)})
        about = set(fact.get("about") or [])
        floor = max([float(v @ player)] if player is not None else [0.0])
        floor = max([floor] + [float(v @ people[a]) for a in about if a in people])
        best = max(((float(v @ pv), k) for k, pv in people.items() if k not in about),
                   default=None)
        if best and best[0] >= ABOUT_NOTE and best[0] > floor:
            notes.append({"fact": fid, "kind": "about", "target": best[1], "score": round(best[0], 2)})
        if consequence_vectors:
            score, cid = max((float(v @ cv), cid) for cid, cv in consequence_vectors.items())
            if score >= CONSEQUENCE_NOTE:
                notes.append({"fact": fid, "kind": "consequence", "target": cid,
                              "score": round(score, 2)})
    return notes


def add_notes(campaign_dir, notes: list[dict]) -> None:
    if not notes:
        return
    path = Path(campaign_dir) / NOTES
    old = _load(path) or []
    tmp = path.with_name(NOTES + ".tmp")
    tmp.write_text(json.dumps(old + notes, indent=1), encoding="utf-8")
    tmp.replace(path)


def _still_open(campaign_dir: Path, note: dict) -> bool:
    """A note the GM acted on since (linked the plot or the person, fired or
    resolved the consequence) is dropped."""
    fact = _facts(campaign_dir).get(note["fact"])
    if fact is None:
        return False
    if note["kind"] == "plot":
        return not fact.get("plots")
    if note["kind"] == "about":
        return note["target"] not in (fact.get("about") or [])
    return any(c.get("id") == note["target"] and not c.get("fired")
               for c in _waiting(campaign_dir))


def lines(campaign_dir) -> list[str]:
    """The notes still open, as lines to print; the file is emptied."""
    campaign_dir = Path(campaign_dir)
    path = campaign_dir / NOTES
    notes = _load(path) or []
    if not notes:
        return []
    with contextlib.suppress(OSError):
        path.unlink()
    waiting = {c["id"]: c for c in _waiting(campaign_dir)}
    out = []
    for n in notes:
        if not _still_open(campaign_dir, n):
            continue
        fid, target = n["fact"], n["target"]
        if n["kind"] == "plot":
            out.append(f"  {fid} looks part of {target} ({n['score']}): "
                       f"bash tools/gm-note.sh plot {fid} --add \"{target}\"")
        elif n["kind"] == "about":
            out.append(f"  {fid} reads like it is about {target} ({n['score']}), but isn't linked: "
                       f"bash tools/gm-note.sh about {fid} --add \"{target}\"")
        else:
            text = waiting.get(target, {}).get("consequence", "")
            out.append(f"  {fid} may fulfil [{target[:4]}] {text} ({n['score']}): "
                       f"bash tools/gm-consequence.sh fire {target} --by {fid}")
    if out:
        out.insert(0, "[NOTE] Semantic recall, about facts recorded before (act on what fits, "
                      "ignore the rest):")
    return out


def main() -> int:
    if sys.argv[1:2] == ["print"] and len(sys.argv) == 3:
        for line in lines(sys.argv[2]):
            print(line)
        return 0
    print("[ERROR] Use: recall_notes.py print <campaign folder>", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
