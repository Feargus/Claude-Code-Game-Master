#!/usr/bin/env python3
"""What semantic recall notices about a fact as it is recorded, printed in the fact's
own output.

The new facts are embedded at once (EmbeddingStore.embed, about a second each with
the model loaded), and each is compared with:

- **the triggers** of the consequences waiting for a fact (`on_fact`): every one that
  scores TRIGGER_NOTE or more is named, with the command to fire it. A recorded fact
  triggers a consequence only when the GM fires it: never by itself;
- **a plot**, when the fact is in none: the open plot it is closest to, if that
  plot is clearly the best (PLOT_NOTE, and PLOT_MARGIN ahead of the next);
- **a person it reads like it is about but isn't linked to** (a missed name
  check: "the clown came back", Pagliacci): ABOUT_NOTE or more, and closer than
  the character and everyone it is linked to already, so a person whose record
  is about the character (a copy of them) isn't suggested for every fact.

A plot or a person from CONFIDENT up is not suggested but linked at once, and the
output says so with the command to undo it: a wrong link costs less than a missing
one. The thresholds are set from playtests (recall-check.log below). A
consequence is only ever named: the GM fires it.

Every comparison worth a look goes into `recall-check.log` in the campaign folder,
for tuning the thresholds: each trigger from LOG_FLOOR,
each plot and person suggestion with its score, and, from gm-consequence.sh, each
consequence the GM fired by a fact (`log_fired`), which says which match was right.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

TRIGGER_NOTE = 0.65         # the Long Hull playtest's nine wrong matches scored 0.51–0.62
PLOT_NOTE, PLOT_MARGIN = 0.45, 0.05
ABOUT_NOTE = 0.55
CONFIDENT = 0.65            # a plot or person linked by itself from here
LOG_FLOOR = 0.40            # triggers logged from here, so the misses show too
LOG = "recall-check.log"


def _load(path: Path):
    import json
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    except ValueError:
        return None


def _log(campaign_dir: Path, lines: list[str]) -> None:
    if not lines:
        return
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(campaign_dir / LOG, "a", encoding="utf-8") as log:
            for line in lines:
                log.write(f"{stamp} {line}\n")
    except OSError:
        pass                                       # the log is for tuning, never in the way


def log_fired(campaign_dir, consequence_id: str, fact_id: str) -> None:
    """The GM fired a consequence by a fact: the right answer for that pair."""
    _log(Path(campaign_dir), [f"fired {consequence_id} by {fact_id}"])


def check_facts(campaign_dir, fact_ids, embedder, skip=()) -> tuple[list[str], list[tuple]]:
    """Embed the new facts and the waiting triggers, compare and log. Returns the
    lines to print and the links to make at once, ("plot" | "about", fact id,
    target), which the lines already announce. `skip`: consequence ids not to
    name (a faction turn's own)."""
    from embedding_store import EmbeddingStore, trigger_texts
    campaign_dir = Path(campaign_dir)
    triggers = trigger_texts(_load(campaign_dir / "consequences.json"))
    keys = [f"fact:{fid}" for fid in fact_ids] + list(triggers)
    vectors = EmbeddingStore(campaign_dir).embed(embedder, keys)
    facts = {f["id"]: f for f in _load(campaign_dir / "facts.json") or []
             if isinstance(f, dict) and f.get("id")}
    store = _load(campaign_dir / "consequences.json") or {}
    effects = {c["id"]: c.get("consequence", "") for c in store.get("active", [])
               if isinstance(c, dict) and c.get("id")}
    plots = {k: p for k, p in (_load(campaign_dir / "plots.json") or {}).items()
             if isinstance(p, dict) and p.get("status", "open") == "open"}
    people = {k: v for k, v in vectors.items() if k.startswith("npc:")}
    player = vectors.get("player")
    out, log, links = [], [], []
    for fid in fact_ids:
        fact, v = facts.get(fid), vectors.get(f"fact:{fid}")
        if fact is None or v is None or fact.get("attitude"):
            continue
        ranked = sorted(((float(v @ vectors[k]), k[8:]) for k in triggers
                         if k in vectors and k[8:] not in skip), reverse=True)
        for score, cid in ranked:
            if score < LOG_FLOOR:
                break
            log.append(f"{fid} trigger {cid} {score:.2f}")
            if score >= TRIGGER_NOTE:
                out.append(f"  {fid} may trigger [{cid[:4]}] \"{triggers['trigger:' + cid]}\" "
                           f"({score:.2f}) → {effects.get(cid, '')}")
                out.append(f"    If it does: bash tools/gm-consequence.sh fire {cid} --by {fid}")
        if not fact.get("plots"):
            ranked = sorted(((float(v @ vectors[f"plot:{k}"]), k) for k in plots
                             if f"plot:{k}" in vectors), reverse=True)
            if ranked:
                gap = ranked[0][0] - ranked[1][0] if len(ranked) > 1 else 1.0
                log.append(f"{fid} plot \"{ranked[0][1]}\" {ranked[0][0]:.2f} (ahead by {gap:.2f})")
                score, plot = ranked[0]
                if score >= CONFIDENT and gap >= PLOT_MARGIN:
                    links.append(("plot", fid, plot))
                    log[-1] += " linked"
                    out.append(f"  {fid} put in {plot} by recall ({score:.2f}); if wrong: "
                               f"bash tools/gm-note.sh plot {fid} --remove \"{plot}\"")
                elif score >= PLOT_NOTE and gap >= PLOT_MARGIN:
                    out.append(f"  {fid} looks part of {plot} ({score:.2f}): "
                               f"bash tools/gm-note.sh plot {fid} --add \"{plot}\"")
        about = set(fact.get("about") or [])
        floor = max([float(v @ player)] if player is not None else [0.0])
        floor = max([floor] + [float(v @ people[a]) for a in about if a in people])
        best = max(((float(v @ pv), k) for k, pv in people.items() if k not in about),
                   default=None)
        if best:
            log.append(f"{fid} about {best[1]} {best[0]:.2f} (linked best {floor:.2f})")
            if best[0] >= CONFIDENT and best[0] > floor:
                links.append(("about", fid, best[1]))
                log[-1] += " linked"
                out.append(f"  {fid} is about {best[1]} too, by recall ({best[0]:.2f}); if wrong: "
                           f"bash tools/gm-note.sh about {fid} --remove \"{best[1]}\"")
            elif best[0] >= ABOUT_NOTE and best[0] > floor:
                out.append(f"  {fid} reads like it is about {best[1]} ({best[0]:.2f}), but isn't "
                           f"linked: bash tools/gm-note.sh about {fid} --add \"{best[1]}\"")
    _log(campaign_dir, log)
    return out, links
