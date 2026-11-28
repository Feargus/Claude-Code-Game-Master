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
  is about the character (a copy of them) isn't suggested for every fact;
- **a consequence still waiting that it reads like** (EVENT_NOTE or more): what
  the consequence is to bring may have happened already, played before its
  trigger, and would then happen twice. The GM resolves it;
- **an earlier fact it repeats** (TWIN_NOTE or more; versions of one truth
  aside): "Seren told Ilaria she is to marry Strake" after the betrothal is on
  record. The GM then tells the earlier fact to those who don't hold it and
  edits the new one down to what is new, or removes it. Not after an edit: an
  edit is mostly the answer to this note, and the note would come again.

A new consequence (a new clock's outcome is one) is compared in the same way with
the consequences still waiting (check_events): one that reads like it may be the
same event, which would then happen twice (the story sped a clock up, and a
consequence now brings what the clock's outcome still will). Two that wait on
the same clock are left out: a sign is meant to resemble the clock's outcome.

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
TWIN_NOTE = 0.80            # What Remains: a repeat 0.83, the next beat of the same scene
                            # (no repeat) 0.70–0.77; the Long Hull's "X told Y …" facts
                            # and their twins 0.66–0.81, which tell --from records now
EVENT_NOTE = 0.60           # What Remains: Dessa's report of the man in the lobby and the
                            # consequence that was to bring him 0.63, any other fact and a
                            # waiting consequence at most 0.53; a consequence and the clock
                            # it overtook 0.69, any other pair at most 0.58
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


def check_facts(campaign_dir, fact_ids, embedder, skip=(),
                twins: bool = True) -> tuple[list[str], list[tuple]]:
    """Embed the new facts and the waiting triggers, compare and log. Returns the
    lines to print and the links to make at once, ("plot" | "about", fact id,
    target), which the lines already announce. `skip`: consequence ids not to
    name (a faction turn's own). `twins`: look for an earlier fact each repeats
    (not after an edit)."""
    from embedding_store import EmbeddingStore, event_texts, trigger_texts
    campaign_dir = Path(campaign_dir)
    store = _load(campaign_dir / "consequences.json") or {}
    triggers = trigger_texts(store)
    events = list(event_texts(store))
    keys = [f"fact:{fid}" for fid in fact_ids] + list(triggers) + events
    vectors = EmbeddingStore(campaign_dir).embed(embedder, keys)
    facts = {f["id"]: f for f in _load(campaign_dir / "facts.json") or []
             if isinstance(f, dict) and f.get("id")}
    effects = {c["id"]: c.get("consequence", "") for c in store.get("active", [])
               if isinstance(c, dict) and c.get("id")}
    plots = {k: p for k, p in (_load(campaign_dir / "plots.json") or {}).items()
             if isinstance(p, dict) and p.get("status", "open") == "open"}
    people = {k: v for k, v in vectors.items() if k.startswith("npc:")}
    player = vectors.get("player")
    from facts import number
    out, log, links = [], [], []
    for fid in fact_ids:
        fact, v = facts.get(fid), vectors.get(f"fact:{fid}")
        if fact is None or v is None or fact.get("attitude"):
            continue
        ranked = sorted(((float(v @ vectors[k]), k[8:]) for k in triggers
                         if k in vectors and k[8:] not in skip), reverse=True)
        named = set(skip)
        for score, cid in ranked:
            if score < LOG_FLOOR:
                break
            log.append(f"{fid} trigger {cid} {score:.2f}")
            if score >= TRIGGER_NOTE:
                named.add(cid)
                out.append(f"  {fid} may trigger {cid} \"{triggers['trigger:' + cid]}\" "
                           f"({score:.2f}) → {effects.get(cid, '')}")
                out.append(f"    If it does: bash tools/gm-consequence.sh fire {cid} --by {fid}")
        out += _happened(campaign_dir, fid, v, vectors, events, named, store, log)
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
        if twins:
            out += _twins(fid, fact, facts, v, vectors, log, number)
    _log(campaign_dir, log)
    return out, links


def _waits(campaign_dir, c) -> str:
    """What a consequence waits for, in words (consequence_manager.trigger_words)."""
    from consequence_manager import trigger_words
    from json_ops import JsonOperations
    ops = JsonOperations(str(campaign_dir))
    return " or ".join(trigger_words(t, ops) for t in c.get("triggers") or []) or "nothing"


def _happened(campaign_dir, fid, v, vectors, events, named, store, log) -> list[str]:
    """The consequences still waiting that a new fact reads like: what each is to
    bring may have happened already, and would then happen again when it fires.
    `named`: consequences this fact may trigger, named already."""
    by_id = {c["id"]: c for c in store.get("active", []) if isinstance(c, dict) and c.get("id")}
    ranked = sorted(((float(v @ vectors[k]), k.partition(":")[2]) for k in events
                     if k in vectors and k.partition(":")[2] not in named), reverse=True)
    if ranked and ranked[0][0] >= LOG_FLOOR:
        log.append(f"{fid} event {ranked[0][1]} {ranked[0][0]:.2f}")
    out = []
    for score, cid in [r for r in ranked if r[0] >= EVENT_NOTE][:2]:
        c = by_id[cid]
        out.append(f"[CHECK] {fid} may be what {cid} waits to bring ({score:.2f}): "
                   f"\"{c.get('consequence', '')}\" (waits for {_waits(campaign_dir, c)})")
        out.append(f"  If it has happened, it won't again: bash tools/gm-consequence.sh "
                   f"resolve {cid}")
    return out


def check_events(campaign_dir, keys, embedder) -> list[str]:
    """A new consequence (keys "consequence:<id>"; a new clock's outcome is one)
    compared with the consequences still waiting: one that reads like it may be
    the same event, which would then happen twice. Two that wait on the same clock
    are left out: a sign is meant to resemble the clock's outcome. One that is a
    clock's outcome (it waits on the clock's last segment) is named as the clock,
    with the commands to move or remove it. Returns the lines to print; logs the
    best."""
    from embedding_store import EmbeddingStore, event_texts
    from threat_clocks import ThreatClockManager, clock_of
    campaign_dir = Path(campaign_dir)
    store = _load(campaign_dir / "consequences.json") or {}
    clocks = _load(campaign_dir / "threat-clocks.json") or {}
    events = event_texts(store)
    vectors = EmbeddingStore(campaign_dir).embed(embedder, list(events))
    by_id = {c["id"]: c for c in store.get("active", []) if isinstance(c, dict) and c.get("id")}
    lower = {str(k).lower(): k for k in clocks}

    def on_clocks(cid):
        return {clock_of(t)[0].lower() for t in (by_id.get(cid) or {}).get("triggers") or []} - {""}

    def outcome_of(cid):
        """The clock whose outcome this consequence is (its last segment), or ''."""
        for t in (by_id.get(cid) or {}).get("triggers") or []:
            name, segment = clock_of(t)
            key = lower.get(name.lower())
            if key is not None and segment == int(clocks[key].get("max", 1)):
                return key
        return ""

    def label(cid):
        clock = outcome_of(cid)
        return f"clock {clock}'s outcome ({cid})" if clock else cid

    out, log = [], []
    for key in keys:
        v, mine = vectors.get(key), key.partition(":")[2]
        if v is None:
            continue
        ranked = sorted(((float(v @ vectors[k]), k.partition(":")[2]) for k in events
                         if k != key and k in vectors
                         and not (on_clocks(mine) & on_clocks(k.partition(":")[2]))), reverse=True)
        if ranked and ranked[0][0] >= LOG_FLOOR:
            log.append(f"{mine} same event {ranked[0][1]} {ranked[0][0]:.2f}")
        for score, cid in [r for r in ranked if r[0] >= EVENT_NOTE][:2]:
            c, clock = by_id[cid], outcome_of(cid)
            if clock:
                cl = clocks[clock]
                out.append(f"[CHECK] {label(mine)} reads like what clock {clock} brings when full "
                           f"({score:.2f}): \"{c.get('consequence', '')}\" (at {cl.get('current', 0)}/"
                           f"{cl.get('max', 1)}{ThreatClockManager.due_text(cl)})")
                out.append(f"  If it speeds that up or replaces it: bash tools/gm-clock.sh due "
                           f"\"{clock}\" --earlier <time>, or bash tools/gm-clock.sh remove \"{clock}\"")
            else:
                out.append(f"[CHECK] {label(mine)} reads like {cid} ({score:.2f}): "
                           f"\"{c.get('consequence', '')}\" (waits for {_waits(campaign_dir, c)})")
                out.append(f"  If they are one event, keep one: bash tools/gm-consequence.sh "
                           f"resolve {cid}, or bash tools/gm-consequence.sh resolve {mine}")
    _log(campaign_dir, log)
    return out


def event_lines(campaign_dir, keys) -> list[str]:
    """check_events for the commands that make a consequence (or a clock with its
    outcome): the lines to print. None without the model (GM_EMBEDDER=off: tests without vectors)."""
    from embedder import get_embedder
    embedder = get_embedder()
    if embedder is None or not keys:
        return []
    return check_events(campaign_dir, keys, embedder)


def _quoted(holder: str) -> str:
    return f'"{holder}"' if " " in holder else holder


def _twins(fid, fact, facts, v, vectors, log, number) -> list[str]:
    """The earlier facts this one repeats, with what to do: tell the earlier one
    to whoever doesn't hold it, and keep only what is new here."""
    root = fact.get("version_of") or fid
    ranked = sorted(((float(v @ vectors[f"fact:{k}"]), k) for k, other in facts.items()
                     if number(other) < number(fact) and f"fact:{k}" in vectors
                     and not other.get("attitude") and (other.get("version_of") or k) != root),
                    reverse=True)
    if ranked and ranked[0][0] >= LOG_FLOOR:
        log.append(f"{fid} repeats {ranked[0][1]} {ranked[0][0]:.2f}")
    out = []
    for score, k in [r for r in ranked if r[0] >= TWIN_NOTE][:2]:
        known = set(facts[k].get("holders") or [])
        missing = [] if "public" in known else [h for h in fact.get("holders") or []
                                                if h not in known]
        out.append(f"[CHECK] {fid} may repeat {k} ({score:.2f}): {facts[k].get('fact', '')}")
        if missing:
            out.append(f"  If it does, tell it: bash tools/gm-note.sh tell {k} "
                       f"{' '.join(_quoted(h) for h in missing)} --from \"<who told them>\"")
            out.append(f"  and keep only what is new: bash tools/gm-note.sh edit {fid} "
                       f"\"<what is new>\", or remove {fid} if nothing is")
        else:
            out.append(f"  They know {k} already. If it does: bash tools/gm-note.sh remove {fid}, "
                       f"or edit {fid} \"<what is new>\"")
    return out
