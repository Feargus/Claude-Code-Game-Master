#!/usr/bin/env python3
"""Note/fact management module for GM tools."""

import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

import facts as fact_file
from campaign_manager import CampaignManager
from game_time import STORED_FORMAT, stored_time
from json_ops import JsonOperations

TRUTH_VALUES = ("partial", "wrong")  # a missing `truth` means true


def check_attitude(raw) -> tuple:
    """(attitude, '') or ('', why it was refused). An attitude is one or more
    adjectives, comma separated ("wary", "fond, exasperated"), never a sentence:
    in the Tidewater playtest the GM wrote whole relationships into it ("a regular
    at Seo's, polite; does not know Dogen beyond sight"), which hid plain facts
    from the player. Empty is fine: not everyone has an attitude."""
    words = [w.strip() for w in str(raw or "").strip().rstrip(".").split(",")]
    words = [w for w in words if w]
    if any(re.search(r"[.;:!?]", w) or len(w.split()) > 2 for w in words):
        return "", (f"The attitude is one or more adjectives, comma separated (\"wary\", "
                    f"\"fond, exasperated\"), not a sentence: '{raw}'. Leave it out for someone "
                    f"with no attitude; what they know, remember or do is its own fact "
                    f"(gm-note.sh).")
    return ", ".join(words), ""


def _person(cid: str, player: str) -> str:
    """An id as a name in a sentence: npc:Mama Seo -> Mama Seo, player -> the player's name."""
    return player if cid == "player" else cid.partition(":")[2] or cid


def current_attitudes(facts: list) -> dict:
    """{(holder id, about id): fact} for the newest attitude of each pair: the one
    that counts. Older ones stay as the record of how it changed."""
    newest = {}
    for f in facts:
        if f.get('attitude') and f.get('holders') and f.get('about'):
            key = (f['holders'][0], f['about'][0])
            if key not in newest or fact_file.number(f) > fact_file.number(newest[key]):
                newest[key] = f
    return newest


def fact_text(entry, player: str = "the character") -> str:
    """A fact's text as the GM should read it, wherever it is shown or searched:
    a secret (holders recorded and empty: nobody knows it) is marked [SECRET], one
    that others know but the player character doesn't is marked [HIDDEN FROM PLAYER],
    a wrong or partial version is marked with the id of the truth. An attitude,
    stored as its adjectives only, is written out: "Mama Seo regards Dogen: fond"
    (`player` is the player character's name; "the character" if not given)."""
    if not isinstance(entry, dict):
        return str(entry)
    text = str(entry.get('fact', entry.get('text', entry.get('event', ''))))
    if entry.get('attitude') and entry.get('holders') and entry.get('about'):
        text = (f"{_person(entry['holders'][0], player)} regards "
                f"{_person(entry['about'][0], player)}: {text}")
    holders = entry.get('holders')
    if holders == []:
        text = f"[SECRET] {text}"
    elif isinstance(holders, list) and not {'player', 'public'} & set(holders):
        text = f"[HIDDEN FROM PLAYER] {text}"     # who knows it: the NPC block
    truth, of = entry.get('truth'), entry.get('version_of')
    if truth == 'wrong':
        return f"[WRONG; the truth is {of}] {text}" if of else f"[WRONG] {text}"
    if truth == 'partial':
        return f"[PARTIAL; fuller: {of}] {text}" if of else f"[PARTIAL] {text}"
    return text


class NoteManager:
    """Manage campaign facts and notes."""

    def __init__(self, world_state_dir: str = "world-state"):
        self.world_state_dir = world_state_dir
        self.last_fired = []  # on_learn consequences fired by the last add_fact / tell
        self.campaign_mgr = CampaignManager(world_state_dir)
        self.campaign_dir = self.campaign_mgr.get_active_campaign_dir()

        if self.campaign_dir is None:
            raise RuntimeError("No active campaign. Run /new-game or /import first.")

        self.json_ops = JsonOperations(str(self.campaign_dir))

        # Ensure facts file exists
        if not (self.campaign_dir / fact_file.FILE).exists():
            fact_file.save(self.json_ops, [])

    def _about(self, fact: str, about=None, not_about=None):
        """(about ids, ids found in the text, errors) for a new fact.

        The ids given are checked; names found in the text are added, except those
        in `not_about`. That is the cross-check: the GM needn't remember who a
        fact names (design-notes.md, "A fact's fields").
        """
        from world_ids import WorldIds
        ids = WorldIds(self.json_ops)
        given, errors = ids.resolve_all(about)
        dropped, more = ids.resolve_all(not_about)
        errors += more
        found = [i for i in ids.mentioned(fact) if i not in given and i not in dropped]
        return [i for i in given if i not in dropped] + found, found, errors

    def _where(self, at=None, nowhere: bool = False, auto: bool = True):
        """(location id or None, errors): where a fact happened. `at` names a
        place; `nowhere` means none (a truth about the world, a secret, something
        off-screen); otherwise, with `auto`, the current location."""
        from world_ids import WorldIds
        if at and nowhere:
            return None, ["Give --at or --nowhere, not both."]
        ids = WorldIds(self.json_ops)
        if at:
            cid, error = ids.resolve_as(at, ("location",))
            return (cid or None), ([f"at: {error}"] if error else [])
        if nowhere or not auto:
            return None, []
        pos = (self.json_ops.load_json("campaign-overview.json") or {}).get("player_position") or {}
        here = pos.get("current_location") if isinstance(pos, dict) else None
        cid, _ = ids.resolve_as(here, ("location",)) if here else ("", "")
        return (cid or None), []

    def _holders(self, holders=None, secret: bool = False, also=None):
        """(holder ids, errors) for a new fact. None = the default: the player and
        the NPCs present; `also` adds to the default. `secret` = nobody (a GM-only
        secret)."""
        from world_ids import WorldIds
        if sum([holders is not None, secret, bool(also)]) > 1:
            return [], ["Give one of --holders (instead of the default), --also (on top "
                        "of it) or --secret (nobody)."]
        if secret:
            return [], []
        ids = WorldIds(self.json_ops)
        if holders is not None:
            return ids.resolve_all(holders, holders=True)
        extra, errors = ids.resolve_all(also, holders=True)
        default = ids.present()
        return default + [h for h in extra if h not in default], errors

    def add_fact(self, fact: str, *, list_waiting: bool = True,
                 about=None, not_about=None, holders=None, secret: bool = False,
                 also=None, truth=None, version_of=None, at=None, nowhere: bool = False,
                 auto_at: bool = True, plots=None, offer_plot: bool = True) -> str:
        """Record a fact. Returns its id, or "" on failure. Everything but the
        text is given by name (a fact has no category any more: facts.py).

        Each fact carries an id, the in-game time it was recorded (`game_time`,
        copied from campaign-overview.json; left out if the campaign has none)
        and the real-world `timestamp`. `about` lists who or what it concerns:
        the ids given plus the names found in the text, minus `not_about`; an
        unknown id refuses the fact. `holders` lists who knows it: by default
        the player and the NPCs present (`also` adds to that); a list given
        replaces it; `secret`
        (or an empty list) means nobody, a GM-only secret. Afterwards it lists
        the consequences waiting on an event, unless `list_waiting` is False.
        `at` is where it happened: the place given, else the current location
        (with `auto_at`), or none with `nowhere`. `plots`: the plots it belongs to;
        with none, and `offer_plot`, the one open plot that involves who or where
        the fact is about is offered (only when exactly one fits).
        """
        about_ids, found, errors = self._about(fact, about, not_about)
        where, more = self._where(at, nowhere, auto_at)
        errors += more
        holder_ids, more = self._holders(holders, secret, also)
        errors += more
        facts = fact_file.load(self.json_ops)
        truth, version_of, version_notes, more = self._check_version(facts, truth, version_of)
        errors += more
        from plot_manager import resolve_plots
        plot_keys, more = resolve_plots(self.json_ops, plots)
        errors += more
        if errors:
            for error in errors:
                print(f"[ERROR] {error}", file=sys.stderr)
            print("[ERROR] Fact not recorded.", file=sys.stderr)
            return ""
        inherited = False
        if version_of and not plot_keys:          # a version belongs where its truth does
            plot_keys = list(self._entry(facts, version_of).get('plots') or [])
            inherited = bool(plot_keys)
        fact_id = fact_file.next_id(facts)
        entry = {'id': fact_id, 'fact': fact}
        if about_ids:
            entry['about'] = about_ids
        entry['holders'] = holder_ids
        if truth:
            entry['truth'] = truth
        if version_of:
            entry['version_of'] = version_of
        if where:
            entry['at'] = where
        if plot_keys:
            entry['plots'] = plot_keys
        game_time = stored_time(self.json_ops)
        if game_time:
            entry['game_time'] = game_time
        entry['timestamp'] = datetime.now(UTC).isoformat()
        facts.append(entry)
        fact_file.save(self.json_ops, facts)

        print(f"[SUCCESS] Recorded fact {fact_id}: {fact}")
        if about_ids:
            which = "all" if found == about_ids else ", ".join(found)
            note = (f" ({which} found in the text; drop a wrong one with "
                    f"gm-note.sh about {fact_id} --remove <id>)") if found else ""
            print(f"  about: {', '.join(about_ids)}{note}")
        print(f"  known to: {', '.join(holder_ids) if holder_ids else 'nobody (a secret)'}")
        if where:
            print(f"  at: {where}")
        if plot_keys:
            print(f"  plot: {', '.join(plot_keys)}"
                  + (f" (as its truth, {version_of})" if inherited else ""))
        elif offer_plot:
            self._offer_plot(fact_id, about_ids + ([where] if where else []))
        for note in version_notes:
            print(f"  {note}")
        if truth:
            print(f"  {fact_text({'truth': truth, 'version_of': entry.get('version_of')}).strip()}")
        if holders is None and not secret:
            self._named_but_absent(fact_id, about_ids, holder_ids)
        from consequence_manager import print_fired
        print_fired(self._learned(fact_id, entry, holder_ids))
        if list_waiting:
            self._list_waiting(fact_id)
        return fact_id

    def set_attitude(self, owner: str, adjectives: str, towards: str = "player") -> str:
        """Record how `owner` (an NPC) regards `towards` (the player or another
        NPC) now: a fact flagged as an attitude, holding only the adjectives,
        known only to the owner. The newest one per pair counts. It is a state,
        not news: no on_learn fires, and it happened nowhere. Returns its id;
        raises ValueError."""
        from world_ids import WorldIds
        ids = WorldIds(self.json_ops)
        who, error = ids.resolve_as(owner, ("npc",))
        if error:
            raise ValueError(error)
        whom, error = ids.resolve_as(towards, ("player", "npc"))
        if error:
            raise ValueError(error)
        if who == whom:
            raise ValueError("An attitude is towards someone else.")
        adjectives, error = check_attitude(adjectives)
        if error or not adjectives:
            raise ValueError(error or "Give the attitude: one or more adjectives (\"wary\").")
        facts = fact_file.load(self.json_ops)
        fact_id = fact_file.next_id(facts)
        entry = {'id': fact_id, 'fact': adjectives, 'attitude': True,
                 'about': [whom], 'holders': [who]}
        game_time = stored_time(self.json_ops)
        if game_time:
            entry['game_time'] = game_time
        entry['timestamp'] = datetime.now(UTC).isoformat()
        facts.append(entry)
        fact_file.save(self.json_ops, facts)
        return fact_id

    def attitudes(self, owner: str) -> dict:
        """{towards id: the current attitude fact} for an NPC; raises ValueError."""
        from world_ids import WorldIds
        who, error = WorldIds(self.json_ops).resolve_as(owner, ("npc",))
        if error:
            raise ValueError(error)
        return {whom: f for (holder, whom), f in
                current_attitudes(fact_file.load(self.json_ops)).items()
                if holder == who}

    def _offer_plot(self, fact_id: str, ids) -> None:
        """The one open plot that involves someone or somewhere the fact is about,
        offered, never given. Nothing when none or several fit."""
        plots = self.json_ops.load_json("plots.json") or {}
        fits = [k for k, p in plots.items() if isinstance(p, dict)
                and (p.get("status") or "open") == "open" and set(ids) & set(p.get("involves") or [])]
        if len(fits) == 1:
            print(f"  Part of {fits[0]}? bash tools/gm-note.sh plot {fact_id} --add \"{fits[0]}\"")

    def set_plots(self, fact_id: str, add=None, remove=None) -> list:
        """Add plots to a recorded fact, or remove them. Returns the new list."""
        from plot_manager import resolve_plots
        adding, errors = resolve_plots(self.json_ops, add)
        removing, more = resolve_plots(self.json_ops, remove)
        if errors + more:
            raise ValueError(" ".join(errors + more))
        facts = fact_file.load(self.json_ops)
        entry = self._entry(facts, fact_id)
        keys = [k for k in entry.get('plots', []) if k not in removing]
        keys += [k for k in adding if k not in keys]
        if keys:
            entry['plots'] = keys
        else:
            entry.pop('plots', None)
        fact_file.save(self.json_ops, facts)
        return keys

    def set_about(self, fact_id: str, add=None, remove=None) -> list:
        """Add ids to, or remove them from, a recorded fact's `about`.
        Returns the new list; raises ValueError for an unknown fact or id."""
        from world_ids import WorldIds
        ids = WorldIds(self.json_ops)
        adding, errors = ids.resolve_all(add)
        removing, more = ids.resolve_all(remove)
        if errors + more:
            raise ValueError("; ".join(errors + more))
        facts = fact_file.load(self.json_ops)
        entry = self._entry(facts, fact_id)
        about = [i for i in entry.get('about', []) if i not in removing]
        about += [i for i in adding if i not in about]
        if about:
            entry['about'] = about
        else:
            entry.pop('about', None)
        fact_file.save(self.json_ops, facts)
        return about

    def _named_but_absent(self, fact_id: str, about_ids, holder_ids) -> None:
        """The scene cross-check: living NPCs a scene fact names who aren't in the
        scene. Either they're here and the GM forgot `gm-scene.sh enter`, or the
        fact is only about them, which is fine."""
        npcs = self.json_ops.load_json("npcs.json") or {}
        absent = [i[4:] for i in about_ids if i.startswith("npc:") and i not in holder_ids
                  and ((npcs.get(i[4:]) or {}).get("status") or {}).get("state") != "dead"]
        if absent:
            names = " ".join(f'"{n}"' for n in absent)
            print(f"  Named but not in the scene: {', '.join(absent)}. If they're here: "
                  f"bash tools/gm-scene.sh enter {names}, then "
                  f"gm-note.sh tell {fact_id} {' '.join('npc:' + n for n in absent)}")

    def _learned(self, fact_id: str, entry: dict, new_holders) -> list:
        """Fire the on_learn consequences for holders who just learned a fact. A fact
        that becomes public is learned by everyone who didn't hold it: the player,
        the street, every living NPC and every faction (todo.md, 2026-11-18). Returns the fired
        consequences (also kept in `last_fired`)."""
        from consequence_manager import ConsequenceManager
        self.last_fired = []
        if not new_holders:
            return []
        about = entry.get('about') or []
        learners = list(new_holders)
        if 'public' in learners:                  # public is everyone: all of them learn it
            from entity_manager import is_dead
            knew = set(entry.get('holders') or []) - set(new_holders)
            npcs = self.json_ops.load_json("npcs.json") or {}
            from factions import load as factions
            everyone = ['player', 'street'] + [f"npc:{k}" for k, v in npcs.items()
                                               if isinstance(v, dict) and not is_dead(v)]
            everyone += [f"faction:{k}" for k in factions(self.json_ops)]
            learners += [w for w in everyone if w not in knew and w not in learners]
        values = []
        for who in learners + ['anyone']:
            values.append(f"{who} learns {fact_id}")
            values += [f"{who} learns about:{a}" for a in about]
        try:
            cm = ConsequenceManager(self.world_state_dir)
        except RuntimeError:
            return []
        who = ("it became public (everyone)" if 'public' in new_holders
               else f"{', '.join(new_holders)} learned")
        self.last_fired = cm.fire_event('on_learn', values, f"{who} {fact_id}: {entry['fact']}")
        return self.last_fired

    def _check_version(self, facts: list, truth=None, version_of=None, fact_id=None):
        """(truth, version_of, notes, errors) for a fact, checked.

        `truth`: None (true), partial or wrong. `version_of`: the fullest true
        version. A version of a version points at its root instead, so the truth
        is always one step away. It can't point at itself, or at a wrong fact
        with no truth behind it. A version needs a truth (partial or wrong).
        """
        errors, notes = [], []
        if truth in ('true', ''):
            truth = None
        if truth is not None and truth not in TRUTH_VALUES:
            errors.append(f"truth is partial or wrong (or true), not {truth!r}.")
        if version_of and truth is None and not errors:
            errors.append("A version of another fact is partial or wrong; give --truth too "
                          "(a true, full version would be the same fact twice).")
        if version_of:
            try:
                target = self._entry(facts, version_of)
            except ValueError as error:
                return truth, None, notes, [str(error)]
            root = target.get('version_of')
            if root:
                notes.append(f"{version_of} is itself a version of {root}; pointing at {root}.")
                version_of, target = root, self._entry(facts, root)
            if version_of == fact_id:
                errors.append("A fact can't be a version of itself.")
            elif target.get('truth') == 'wrong':
                errors.append(f"{version_of} is marked wrong; version_of points at the truth.")
        return truth, version_of, notes, errors

    def set_truth(self, fact_id: str, truth=None, version_of=None, keep_version=True) -> dict:
        """Mark a recorded fact true (None), partial or wrong, and/or link it to
        the fullest true version. Returns the entry; raises ValueError."""
        facts = fact_file.load(self.json_ops)
        entry = self._entry(facts, fact_id)
        if keep_version and version_of is None:
            version_of = entry.get('version_of')
        truth, version_of, notes, errors = self._check_version(facts, truth, version_of, fact_id)
        if any(f.get('version_of') == fact_id for f in facts) and (truth == 'wrong' or version_of):
            errors.append(f"Other facts are versions of {fact_id}; it is their truth.")
        if errors:
            raise ValueError(" ".join(errors))
        for key, value in (('truth', truth), ('version_of', version_of)):
            if value:
                entry[key] = value
            else:
                entry.pop(key, None)
        if version_of and not entry.get('plots') and self._entry(facts, version_of).get('plots'):
            entry['plots'] = list(self._entry(facts, version_of)['plots'])    # as its truth
            notes.append(f"plot: {', '.join(entry['plots'])} (as its truth, {version_of})")
        fact_file.save(self.json_ops, facts)
        for note in notes:
            print(f"  {note}")
        return entry

    def _entry(self, facts: list, fact_id: str) -> dict:
        entry = fact_file.by_id(facts, fact_id)
        if entry is None:
            raise ValueError(f"No fact '{fact_id}'.")
        return entry

    def tell(self, fact_id: str, holders) -> list:
        """Someone learns a recorded fact: add holders. Returns those who are new
        (already knowing isn't learning). Raises ValueError for an unknown fact or id."""
        from world_ids import WorldIds
        adding, errors = WorldIds(self.json_ops).resolve_all(holders, holders=True)
        if errors:
            raise ValueError("; ".join(errors))
        facts = fact_file.load(self.json_ops)
        entry = self._entry(facts, fact_id)
        known = entry.setdefault('holders', [])
        new = [h for h in adding if h not in known]
        self.last_fired = []
        if new:
            known.extend(new)
            fact_file.save(self.json_ops, facts)
            self._learned(fact_id, entry, new)
        return new

    def remove_facts(self, fact_ids) -> int:
        """Delete the facts with these ids (undoing a world tick). Returns how many."""
        ids = set(fact_ids)
        facts = fact_file.load(self.json_ops)
        kept = [f for f in facts if f.get('id') not in ids]
        if len(kept) != len(facts):
            fact_file.save(self.json_ops, kept)
        return len(facts) - len(kept)

    def _list_waiting(self, fact_id: str) -> None:
        """Show the consequences waiting on an event, so the GM can judge whether
        the new fact fulfils one (design-notes.md, "World state")."""
        from consequence_manager import ConsequenceManager, print_waiting
        try:
            waiting = ConsequenceManager(self.world_state_dir).waiting_on_event()
        except RuntimeError:
            return
        print_waiting(fact_id, waiting)

    # ---------- looking facts up ----------

    def _all(self) -> list:
        """Every fact, newest first (by the number in its id); copies, so a
        lookup can mark them without changing the file's."""
        return [dict(f) for f in fact_file.newest_first(fact_file.load(self.json_ops))]

    def show(self, fact_ids) -> list:
        """The facts with these ids, each with `versions`: the ids of the facts
        that are versions of it. Raises ValueError for an unknown id."""
        everything = self._all()
        by_id = {f.get('id'): f for f in everything}
        out = []
        for fid in fact_ids:
            if fid not in by_id:
                raise ValueError(f"No fact '{fid}'.")
            entry = dict(by_id[fid])
            entry['versions'] = [f['id'] for f in everything if f.get('version_of') == fid]
            out.append(entry)
        return out

    def find(self, held_by=None, about=None, secret=False, hidden=False, truth=None,
             text=None, at=None, since=None, until=None, plot=None) -> list:
        """Facts matching every filter given, newest first.

        held_by: holder ids (or names); each must know it, and a fact held by
        `public` counts as known to everyone (`street` doesn't: who belongs to
        the street isn't recorded). about: ids it must be about. secret: nobody
        knows it. hidden: the player doesn't. truth: wrong or partial. text:
        every word must occur. Matching facts get `public: True` when only
        `public` made a held_by match. Raises ValueError for an unknown id.
        """
        from world_ids import WorldIds
        ids = WorldIds(self.json_ops)
        holders, errors = ids.resolve_all(held_by, holders=True)
        abouts, more = ids.resolve_all(about)
        errors += more
        place = None
        if at:
            place, error = ids.resolve_as(at, ("location",))
            errors += [error] if error else []
        plot_key = ""
        if plot:
            from plot_manager import resolve_plots
            keys, more = resolve_plots(self.json_ops, [plot])
            errors += more
            plot_key = keys[0] if keys else ""
        if errors:
            raise ValueError("; ".join(errors))
        words = [w.lower() for w in str(text or '').split()]
        out = []
        for f in self._all():
            known = f.get('holders')
            if holders:
                if known is None or not all(h in known or 'public' in known for h in holders):
                    continue
                if any(h not in known for h in holders):
                    f = dict(f, public=True)
            if abouts and not all(a in (f.get('about') or []) for a in abouts):
                continue
            if secret and known != []:
                continue
            if hidden and (known is None or {'player', 'public'} & set(known)):
                continue
            if truth and f.get('truth') != truth:
                continue
            if words and not all(w in str(f.get('fact', '')).lower() for w in words):
                continue
            if place and f.get('at') != place:
                continue
            if plot_key and plot_key not in (f.get('plots') or []):
                continue
            when = str(f.get('game_time') or '')
            if (since or until) and not when:
                continue
            if since and when < since or until and when > until:
                continue
            out.append(f)
        return out

    def witness(self, who: str, at=None, since=None, until=None, include=None,
                dry_run: bool = False) -> dict:
        """Someone was there: they learn the facts recorded at a place (default:
        the current location), optionally within a game-time window.

        Taught by default: what happened in the open there, the facts the player
        or the public holds (except the player's wrong beliefs). Not taught, only
        suggested: secrets, facts only others hold, wrong beliefs; `include`
        adds chosen ones (the GM decides what this person could have perceived).
        Facts they hold already are skipped. Returns {"who", "taught",
        "suggested"} as lists of facts; with `dry_run` nothing is changed.
        Raises ValueError.
        """
        from time_manager import parse_time
        from world_ids import WorldIds
        cid, error = WorldIds(self.json_ops).resolve_as(who, ("npc",))
        if error:
            raise ValueError(error)
        if at is None:
            place, errors = self._where()
            if not place:
                raise ValueError("Where were they? The current location is unknown; give --at.")
            at = place
        window = [parse_time(t).strftime(STORED_FORMAT) if t else None for t in (since, until)]
        candidates = [f for f in self.find(at=at, since=window[0], until=window[1])
                      if cid not in (f.get('holders') or [])]
        def seen(f):
            known = f.get('holders')
            return (isinstance(known, list) and bool({'player', 'public'} & set(known))
                    and f.get('truth') != 'wrong')
        chosen = set(include or [])
        unknown = chosen - {f['id'] for f in candidates}
        if unknown:
            raise ValueError(f"Not among the facts at that place (or known already): "
                             f"{', '.join(sorted(unknown))}.")
        taught = [f for f in candidates if seen(f) or f['id'] in chosen]
        suggested = [f for f in candidates if f not in taught]
        self.last_fired = []
        if not dry_run:
            fired = []
            for f in reversed(taught):  # oldest first, as they happened
                self.tell(f['id'], [cid])
                fired += self.last_fired
            self.last_fired = fired
        return {"who": cid, "taught": taught, "suggested": suggested}

    def beat(self, items) -> list:
        """Several facts of one beat at once, all checked before any is written.

        Each item is a fact as `add` takes it ({"fact", "about", "not_about",
        "holders", "also", "secret", "truth", "version_of", "at", "nowhere",
        "plot"}; "plot" is one plot's name or a list, as `--plot` is on the
        command line, the opening and the world tick); `version_of` may name an
        earlier item of the same call as
        "#1", "#2", ... (a deception: the truth first, then the false impression
        the fooled one holds). Returns the new ids; raises ValueError and writes
        nothing if any item is refused.
        """
        allowed = {"fact", "about", "not_about", "holders", "also", "secret",
                   "truth", "version_of", "at", "nowhere", "plot"}
        def as_list(value):
            return None if value is None else [value] if isinstance(value, str) else list(value)
        if not isinstance(items, list) or not items:
            raise ValueError("A beat is a JSON list of facts.")
        facts = fact_file.load(self.json_ops)
        errors = []
        for n, item in enumerate(items, 1):
            where = f"fact #{n}"
            if not isinstance(item, dict) or not str(item.get("fact") or "").strip():
                errors.append(f"{where} needs a \"fact\".")
                continue
            extra = set(item) - allowed
            if "category" in extra:
                errors.append(f"{where}: facts have no category any more; leave \"category\" out.")
                extra.discard("category")
            if "plots" in extra:
                errors.append(f"{where}: the field is \"plot\" (one name, or a list), "
                              f"as on the command line (--plot).")
                extra.discard("plots")
            if extra:
                errors.append(f"{where}: unknown field(s) {', '.join(sorted(extra))}.")
            _, _, more = self._about(item["fact"], as_list(item.get("about")),
                                     as_list(item.get("not_about")))
            errors += [f"{where}: {e}" for e in more]
            _, more = self._holders(as_list(item.get("holders")), bool(item.get("secret")),
                                    as_list(item.get("also")))
            errors += [f"{where}: {e}" for e in more]
            _, more = self._where(item.get("at"), bool(item.get("nowhere")))
            errors += [f"{where}: {e}" for e in more]
            ref = str(item.get("version_of") or "")
            if ref.startswith("#"):
                k = int(ref[1:]) if ref[1:].isdigit() else 0
                if not 1 <= k < n:
                    errors.append(f"{where}: version_of {ref} must name an earlier fact of this beat.")
                elif not item.get("truth"):
                    errors.append(f"{where}: a version is partial or wrong; give \"truth\".")
                elif (items[k - 1] or {}).get("truth") == "wrong":
                    errors.append(f"{where}: {ref} is marked wrong; version_of points at the truth.")
            else:
                _, _, _, more = self._check_version(facts, item.get("truth"), ref or None)
                errors += [f"{where}: {e}" for e in more]
        if errors:
            raise ValueError(" ".join(errors))
        written = []
        for item in items:
            ref = str(item.get("version_of") or "")
            if ref.startswith("#"):
                ref = written[int(ref[1:]) - 1]
            fid = self.add_fact(item["fact"], list_waiting=False, about=as_list(item.get("about")),
                                not_about=as_list(item.get("not_about")),
                                holders=as_list(item.get("holders")),
                                secret=bool(item.get("secret")), also=as_list(item.get("also")),
                                truth=item.get("truth"), version_of=ref or None,
                                at=item.get("at"), nowhere=bool(item.get("nowhere")),
                                plots=as_list(item.get("plot")))
            if not fid:
                self.remove_facts(written)
                raise ValueError("A fact was refused (see above); none of this beat was kept.")
            written.append(fid)
        self._list_waiting(", ".join(written))
        return written


def fact_line(f: dict) -> str:
    """One fact on one line: id, game time, the marked text in full (a fact cut
    short can drop its turn), who it's about and who knows it."""
    text = fact_text(f)
    when = str(f.get('game_time', '')).replace('T', ' ')
    known = f.get('holders')
    who = ("who knows it isn't recorded" if known is None else
           f"known to: {', '.join(known) or 'nobody'}")
    if f.get('public'):
        who += " (public: everyone)"
    about = f"about: {', '.join(f['about'])}; " if f.get('about') else ""
    at = f"at: {f['at']}; " if f.get('at') else ""
    return f"{f.get('id')} [{when or 'no game time'}] {text}  ({at}{about}{who})"


def fact_details(f: dict) -> str:
    """A fact in full, with its truth and its versions."""
    lines = [f"{f.get('id')} ({str(f.get('game_time') or 'no game time').replace('T', ' ')})",
             f"  {fact_text(f)}"]
    if f.get('at'):
        lines.append(f"  at: {f['at']}")
    if f.get('about'):
        lines.append(f"  about: {', '.join(f['about'])}")
    known = f.get('holders')
    lines.append("  known to: " + ("not recorded (an old fact)" if known is None else
                                   ', '.join(known) or "nobody (a secret)"))
    if f.get('truth'):
        lines.append(f"  truth: {f['truth']}" + (f", a version of {f['version_of']}"
                                                  if f.get('version_of') else ""))
    if f.get('versions'):
        lines.append(f"  versions of it: {', '.join(f['versions'])}")
    return "\n".join(lines)


NARROW = ('gm-note.sh find --about "npc:<who>" --at "<where>" (or --plot "<plot>", '
          '--held-by "<who>"; filters combine)')


def _print_found(found: list, limit: int, filtered: bool = True) -> None:
    """The facts, newest first, at most `limit` (0: all). A longer list ends
    with how to narrow it: lists stay short when lookups are filtered."""
    shown = found if limit <= 0 else found[:limit]
    for f in shown:
        print(fact_line(f))
    if not found:
        print("No facts match.")
    elif len(found) > len(shown):
        more = len(found) - len(shown)
        if filtered:
            print(f"+{more} more: add another filter, or --limit 0 for all")
        else:
            print(f"+{more} older: narrow it with {NARROW}")


def main():
    """CLI interface for note management."""
    import argparse
    parser = argparse.ArgumentParser(description="Facts")
    sub = parser.add_subparsers(dest="action")
    p = sub.add_parser("add", help="record a fact")
    p.add_argument("fact")
    p.add_argument("more", nargs="*", help=argparse.SUPPRESS)   # the old form: <category> <fact>
    p.add_argument("--about", action="append", default=[],
                   help="who or what it concerns (repeatable): player, npc:<name>, location:<name>")
    p.add_argument("--not-about", dest="not_about", action="append", default=[],
                   help="a name found in the text that the fact is not about")
    p_add = p
    p_add.add_argument("--holders", action="append",
                       help="who knows it (repeatable), instead of the default: the player "
                            "and the NPCs present. player, npc:<name>, street, public")
    p_add.add_argument("--also", action="append",
                       help="who else knows it, on top of the default (repeatable)")
    p_add.add_argument("--secret", action="store_true", help="nobody knows it (GM only)")
    p_add.add_argument("--truth", choices=list(TRUTH_VALUES),
                       help="partial (true, but leaves things out) or wrong; default true")
    p_add.add_argument("--version-of", dest="version_of",
                       help="the id of the fullest true version of this fact")
    p_add.add_argument("--at", help="where it happened (default: the current location)")
    p_add.add_argument("--nowhere", action="store_true",
                       help="it happened nowhere in particular (a truth, a secret, off-screen)")
    p_add.add_argument("--plot", action="append", dest="plots", default=[],
                       help="the plot it belongs to (repeatable)")
    p = sub.add_parser("plot", help="add a recorded fact to a plot, or take it out")
    p.add_argument("fact_id")
    p.add_argument("--add", action="append", default=[])
    p.add_argument("--remove", action="append", default=[])
    p = sub.add_parser("truth", help="mark a recorded fact true, partial or wrong")
    p.add_argument("fact_id")
    p.add_argument("truth", choices=["true"] + list(TRUTH_VALUES))
    p.add_argument("--version-of", dest="version_of")
    p.add_argument("--no-version", dest="no_version", action="store_true",
                   help="drop the link to the true version")
    p = sub.add_parser("tell", help="someone learns a recorded fact")
    p.add_argument("fact_id")
    p.add_argument("holders", nargs="+")
    p = sub.add_parser("about", help="change a recorded fact's about")
    p.add_argument("fact_id")
    p.add_argument("--add", action="append", default=[])
    p.add_argument("--remove", action="append", default=[])
    p = sub.add_parser("show", help="facts in full, by id")
    p.add_argument("fact_ids", nargs="+")
    p = sub.add_parser("find", help="facts by who knows them, who they are about, ...")
    p.add_argument("--held-by", dest="held_by", action="append", default=[],
                   help="who knows it (repeatable; public facts count, street ones don't)")
    p.add_argument("--about", action="append", default=[], help="who or what it concerns (repeatable)")
    p.add_argument("--secret", action="store_true", help="nobody knows it")
    p.add_argument("--hidden", action="store_true", help="the player doesn't know it")
    p.add_argument("--truth", choices=list(TRUTH_VALUES))
    p.add_argument("--text", help="words that must all occur in it")
    p.add_argument("--at", help="where it happened")
    p.add_argument("--plot", help="the plot it belongs to")
    p.add_argument("--limit", type=int, default=10, help="how many (0: all); newest first")
    p.add_argument("--like", metavar="QUESTION",
                   help="rank by meaning, best first (recall.py): --held-by, --hidden, --secret, "
                        "--truth, --text still filter; --about, --at, --plot only "
                        "raise a fact's rank")
    p = sub.add_parser("beat", help="several facts of one beat at once")
    p.add_argument("facts", nargs="?", help='JSON list: [{"fact": ..., "holders": [...], ...}, ...]; '
                                 'version_of may be "#1" (an earlier fact of this beat). '
                                 "Left out: read from after the command (<<'EOF' ... EOF)")
    p = sub.add_parser("witness", help="someone was there: they learn what happened at a place")
    p.add_argument("who")
    p.add_argument("--at", help="the place (default: the current location)")
    p.add_argument("--from", dest="since", help='game time "YYYY-MM-DD HH:MM"')
    p.add_argument("--to", dest="until", help='game time "YYYY-MM-DD HH:MM"')
    p.add_argument("--include", action="append", default=[],
                   help="also teach this suggested fact (a secret, a fact only others hold)")
    p.add_argument("--dry-run", dest="dry_run", action="store_true", help="only list")
    p = sub.add_parser("recent", help="the latest facts")
    p.add_argument("count", type=int, nargs="?", default=10)
    from cli_output import strip_json_flag, wants_json
    json_mode = wants_json()
    args = parser.parse_args(strip_json_flag(sys.argv[1:]))
    if not args.action:
        parser.print_help()
        sys.exit(1)

    try:
        manager = NoteManager()
        if args.action == 'add':
            if args.more:
                raise ValueError(
                    f"A fact has no category any more: gm-note.sh \"<the fact>\" [--about ...]. "
                    f"Got {1 + len(args.more)} texts, the first \"{args.fact}\"; nothing was recorded.")
            if len(args.fact.split()) < 2:
                raise ValueError(
                    f"A fact is a sentence, and \"{args.fact}\" is one word; nothing was recorded. "
                    f"gm-note.sh \"<the fact>\", or one of: tell, about, plot, truth, beat, "
                    f"witness, show, find, recent.")
            if not manager.add_fact(args.fact,
                                    about=args.about, not_about=args.not_about,
                                    holders=args.holders, secret=args.secret,
                                    also=args.also, truth=args.truth,
                                    version_of=args.version_of, at=args.at,
                                    nowhere=args.nowhere, plots=args.plots):
                sys.exit(1)
        elif args.action == 'truth':
            entry = manager.set_truth(args.fact_id, args.truth, args.version_of,
                                      keep_version=not args.no_version)
            print(f"{args.fact_id}: {fact_text(entry)}")
        elif args.action == 'tell':
            new = manager.tell(args.fact_id, args.holders)
            print(f"{args.fact_id}: {', '.join(new)} now know(s) it" if new else
                  f"{args.fact_id}: they knew it already")
            from consequence_manager import print_fired
            print_fired(manager.last_fired)
        elif args.action == 'plot':
            keys = manager.set_plots(args.fact_id, args.add, args.remove)
            print(f"{args.fact_id} plots: {', '.join(keys) or '(none)'}")
        elif args.action == 'about':
            about = manager.set_about(args.fact_id, args.add, args.remove)
            print(f"{args.fact_id} about: {', '.join(about) or '(nothing)'}")
        elif args.action == 'beat':
            from cli_output import json_input
            written = manager.beat(json_input(args.facts, "the beat"))
            print(f"[SUCCESS] Recorded {', '.join(written)}")
        elif args.action == 'witness':
            result = manager.witness(args.who, args.at, args.since, args.until,
                                     args.include, args.dry_run)
            verb = "would learn" if args.dry_run else "learned"
            print(f"{result['who']} {verb} {len(result['taught'])} fact(s):")
            for f in result['taught']:
                print(f"  {fact_line(f)}")
            if result['suggested']:
                print("Not taught (secrets, facts only others hold, wrong beliefs): add any this "
                      "person could have perceived with --include <id>, or later gm-note.sh tell:")
                for f in result['suggested']:
                    print(f"  {fact_line(f)}")
            from consequence_manager import print_fired
            print_fired(manager.last_fired)
        elif args.action in ('show', 'find', 'recent'):
            if args.action == 'show':
                found = manager.show(args.fact_ids)
            elif args.action == 'find' and args.like:
                from recall import find_like, print_found
                result = find_like(manager, args.like, args.limit, args.held_by, args.about,
                                   args.secret, args.hidden, args.truth,
                                   args.text, args.at, plot=args.plot)
                if json_mode:
                    print(json.dumps(result, indent=2, ensure_ascii=False))
                else:
                    print_found(result, fact_line)
                return
            elif args.action == 'find':
                found = manager.find(args.held_by, args.about, args.secret, args.hidden,
                                     args.truth, args.text, args.at, plot=args.plot)
            else:
                found = manager.find()
                if json_mode:
                    found = found[:max(0, args.count)]
            if json_mode:
                print(json.dumps(found, indent=2, ensure_ascii=False))
            elif args.action == 'show':
                print("\n\n".join(fact_details(f) for f in found))
            elif args.action == 'recent':
                _print_found(found, max(1, args.count), filtered=False)
            else:
                given = (args.held_by, args.about, args.secret, args.hidden, args.truth,
                         args.text, args.at, args.plot)
                _print_found(found, args.limit, filtered=any(given))
    except (RuntimeError, ValueError) as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
