#!/usr/bin/env python3
"""The session brief: what the GM reads at the start of a session.

`gm-session.sh context` prints it (SessionManager.get_full_context hands over to
`Brief.text`). It reads the campaign's files and writes nothing.
"""

import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from consequence_manager import describe_effects
from entity_manager import is_party_member, npcs_present, npcs_usually_at
from note_manager import fact_text
from schemas import PLOT_TYPE_SORT
from threat_clocks import ThreatClockManager
from world_kit import WorldKit


class Brief:
    """The brief for one campaign, built from a SessionManager's view of it."""

    # The sections in the order they are printed: each is a method
    # `_section_<name>` returning its lines ([] when it has nothing to show).
    SECTIONS = ("header", "kit", "play_style", "images", "voice", "world_index",
                "previously_on", "world_remembers", "story_threads", "ready_threads",
                "key_facts", "wrong_beliefs", "clocks", "character", "party", "people",
                "usual", "pending", "world_rules", "systems")

    def __init__(self, session):
        self.session = session
        self.json_ops = session.json_ops
        self.campaign_dir = session.campaign_dir
        self.campaign_file = session.campaign_file
        self.character_file = session.character_file
        self.session_log = session.session_log
        self._wsd = session._wsd

    # What the brief asks of the session (kept there: moves and session ends use them).
    def get_preferences(self) -> dict[str, Any]:
        return self.session.get_preferences()

    def _scene(self):
        return self.session._scene()

    def _get_session_number(self) -> int:
        return self.session._get_session_number()

    def _latest_session_meta(self) -> dict[str, str]:
        return self.session._latest_session_meta()

    @staticmethod
    def _normalize_connection_list(connections):
        from session_manager import SessionManager
        return SessionManager._normalize_connection_list(connections)

    def text(self, full: bool = False) -> str:
        return self.get_full_context(full=full)

    def _truncate(self, text: str, limit: int, full: bool) -> str:
        """Trim long text in compact context mode."""
        if full or not text or len(text) <= limit:
            return text
        return text[:limit - 3].rstrip() + "..."

    @staticmethod
    def _remainder(hidden: int, noun: str, hint: str) -> str | None:
        """Disclosure line for a truncated list: '+N more <noun> — <hint>'."""
        if hidden <= 0:
            return None
        return f"+{hidden} more {noun} — {hint}"

    def _place_lines(self, location: str) -> list[str]:
        """The current place as recorded, narrated from: its description and its
        exits. A place with no description says how to write one first."""
        place = (self.json_ops.load_json("locations.json") or {}).get(location)
        if not isinstance(place, dict):
            return []
        description = str(place.get("description") or "").strip()
        lines = [f"Here: {description}" if description else
                 f"Here: (no description yet: write one before narrating the place, "
                 f"bash tools/gm-location.sh describe \"{location}\" \"...\")"]
        exits, _ = self._normalize_connection_list(place.get("connections", []))
        if exits:
            lines.append("Exits: " + "; ".join(
                f"{c['to']} ({c['path']})" if c.get("path") else c["to"] for c in exits))
        return lines


    def get_full_context(self, full: bool = False) -> str:
        """The whole brief: each section in turn. Some sections leave what they
        loaded or showed for later ones (the location, the character, the
        session summaries already printed)."""
        self.full = full
        lines = []
        for section in self.SECTIONS:
            lines += getattr(self, f"_section_{section}")()
        context = "\n".join(lines)

        # Token observability: soft ~2k-token target is GUIDANCE only, never a hard
        # cut. Opt in with DM_DEBUG_CONTEXT=1 to watch the budget without altering output.
        if os.environ.get('DM_DEBUG_CONTEXT'):
            approx_tokens = len(context) // 4
            print(f"[context] ~{approx_tokens} tokens ({len(context)} chars)", file=sys.stderr)

        return context

    def _section_header(self) -> list[str]:
        lines = []

        # --- Campaign header ---
        campaign = self.json_ops.load_json(self.campaign_file) or {}
        campaign_name = campaign.get('name', campaign.get('campaign_name', 'Unknown Campaign'))
        session_num = self._get_session_number()
        location = campaign.get('player_position', {}).get('current_location', 'Unknown')
        time_of_day = campaign.get('time', {}).get('time_of_day', campaign.get('time_of_day', ''))
        current_date = campaign.get('time', {}).get('current_date', campaign.get('current_date', ''))
        game_time = campaign.get('game_time') or ''
        if len(game_time) >= 16:
            time_of_day = f"{time_of_day} ({game_time[11:16]})"
        time_str = f"{time_of_day}, {current_date}" if time_of_day and current_date else time_of_day or current_date or 'Unknown'

        lines.append("=== SESSION CONTEXT ===")
        lines.append(f"Campaign: {campaign_name} | Session #{session_num}")
        lines.append(f"Location: {location} | Time: {time_str}")
        lines.extend(self._place_lines(location))
        self.campaign = campaign
        self.location = location
        return lines

    def _section_kit(self) -> list[str]:
        lines = []
        # --- KIT (ambient; skills defer here instead of calling world_kit.py info) ---
        kit = None
        try:
            kit = WorldKit(self._wsd)
            if kit.campaign_dir is None:
                kit = None
        except Exception:
            kit = None
        if kit is not None:
            skills = kit.skills()
            vitals = kit.vitals()
            lines.append("")
            lines.append("--- KIT ---")
            lines.append(f"name: {kit.name()}")
            lines.append(f"vitals: {', '.join(vitals) if vitals else '(none)'}")
            lines.append(f"skills: {', '.join(skills) if skills else 'the standard list (gm-skills)'}")
        self.kit = kit
        return lines

    def _section_play_style(self) -> list[str]:
        lines = []
        # --- Play style: only what differs from the defaults CLAUDE.md states ---
        # (action menu on, adaptive pacing, no book inspiration, no images). A line
        # that only repeated CLAUDE.md cost 300 tokens a brief and drifted from it.
        prefs = self.get_preferences()
        if prefs.get("beat_length", "adaptive") == "tight":
            lines.append("Pacing: TIGHT — a beat is the player's action, its immediate "
                         "consequence, and AT MOST ONE new world development. Then stop at "
                         "the first moment the player could plausibly act. Scene-state "
                         "changes (distance closing, arrivals, reveals, an NPC deciding "
                         "something new) do not happen on their own — each waits for a "
                         "player action to carry it, and each is its own beat. Before "
                         "sending, test: could the player reasonably say 'wait — I do X' "
                         "anywhere in this reply? If yes, cut there. Keep prose short: a few "
                         "sentences to a short paragraph.")
        if prefs.get("rag_inspiration", False):
            lines.append("Inspiration: every beat (or every other beat), run "
                         "`gm-search.sh \"<what's happening now>\" --rag-only` and mine the "
                         "returned passages for a concrete image, phrase, or sensory detail "
                         "from the source. Synthesize — never paste raw passages.")
        if not prefs.get("action_menu", True):
            lines.append("Play style: action menu OFF — end beats with an open prompt; do "
                         "NOT list numbered choices. The player drives freely. "
                         "(Toggle: /gm choices on|off)")
        return lines

    def _section_images(self) -> list[str]:
        lines = []
        # --- Scene images (gpt-image-2): only when a key is configured ---
        if os.environ.get("OPENAI_API_KEY"):
            lines.append("Scene images: ENABLED — illustrate GENEROUSLY and with glee "
                         "(images cost ~$0.04; lean toward YES). New location, monster/boss "
                         "reveal, big loot, a styled flourish, a funny beat, a quiet vista — "
                         "any beat with a real visual or emotional charge earns one. Present "
                         "it DIEGETICALLY: frame the picture as an artifact made by an in-world "
                         "chronicler whose style fits this world's voice (e.g. \"BEHOLD, the "
                         "battle as set down by the scholar Astreus —\") and keep that same "
                         "artist + art-style across the campaign so it reads like one artbook. "
                         "Run `bash tools/gm-image.sh generate --title \"...\" --prompt \"...\"`, "
                         "then show the file:// link. (See gm-craft → Diegetic Illustration.) "
                         "Skip only truly flat beats and don't re-shoot the same static room.")
            chronicler = self.json_ops.load_json("chronicler.json") or {}
            if chronicler.get("name"):
                bits = [f"This campaign's chronicler is {chronicler['name']}"]
                if chronicler.get("persona"):
                    bits.append(f"({chronicler['persona']})")
                line = " ".join(bits) + "."
                if chronicler.get("style"):
                    line += (f" Locked art style: {chronicler['style']} "
                             "(auto-added to every prompt).")
                line += " Frame every image as their work and keep them consistent."
                lines.append("  Chronicler: " + line)
            else:
                lines.append("  Chronicler: none yet — name one the first time you "
                             "illustrate and persist it with `bash tools/gm-image.sh "
                             "chronicler --name \"...\" --style \"...\" --persona \"...\"`.")
        return lines

    def _section_voice(self) -> list[str]:
        lines = []
        full = self.full
        # --- Narrative Voice (write the prose in the world's authorial voice) ---
        bible = self.json_ops.load_json("world-bible.json") or {}
        voice = bible.get("voice") or {}
        style = (voice.get("style") or "").strip()
        passages = [str(p).strip() for p in (voice.get("sample_passages") or []) if str(p).strip()]
        from glossary import terms as glossary_terms
        words = glossary_terms(self.json_ops)
        if style or passages or words:
            lines.append("")
            lines.append("--- NARRATIVE VOICE (narrate in this voice; a prose target, NOT lore) ---")
            if style:
                lines.append(f"Style: {style}")
            if words:
                lines.append("The world's own words (what one means: gm-glossary.sh show "
                             "\"<term>\"): " + ", ".join(words))
            shown_passages = passages if full else passages[:3]
            for p in shown_passages:
                lines.append(f"  | {p}")
            rem = None if full else self._remainder(
                len(passages) - len(shown_passages), "sample passages", "--full")
            if rem:
                lines.append(rem)
        self.bible = bible
        return lines

    def _section_world_index(self) -> list[str]:
        lines = []
        bible = self.bible
        # --- World Index (named things that exist; scan before inventing a name) ---
        index = bible.get("index") or {}
        index_labels = (
            ("npcs", "NPCs"), ("locations", "Locations"),
            ("items", "Items"), ("monsters", "Monsters"),
        )
        index_lines: list[str] = []
        for bucket, label in index_labels:
            entries = [e for e in (index.get(bucket) or []) if isinstance(e, dict) and e.get("name")]
            if not entries:
                continue
            index_lines.append(f"{label}:")
            for e in entries:
                note = str(e.get("note") or "").strip()
                index_lines.append(f"  {e['name']}" + (f" — {note}" if note else ""))
        if index_lines:
            lines.append("")
            lines.append("--- WORLD INDEX (named things that exist; scan before inventing a name) ---")
            lines.extend(index_lines)
        return lines

    def _section_previously_on(self) -> list[str]:
        lines = []
        full = self.full
        # --- Previously On (story spine: resume story-aware, not stat-amnesiac) ---
        # Bounded by item COUNT, never by chopping a single entry. --full shows all.
        all_summaries = self._recent_session_summaries(n=None)
        summaries = all_summaries if full else all_summaries[-3:]
        if summaries:
            lines.append("")
            lines.append("--- PREVIOUSLY ON ---")
            for s in summaries:
                lines.append(f"- {s}")
            rem = None if full else self._remainder(
                len(all_summaries) - len(summaries), "sessions",
                "--full or session-log.md")
            if rem:
                lines.append(rem)
            meta = self._latest_session_meta()
            cliff = meta.get('cliffhanger') or self._cliffhanger(summaries[-1])
            if cliff:
                lines.append(f"WHERE WE PAUSED: {cliff}")
            if meta.get('open_threads'):
                lines.append(f"OPEN THREADS: {meta['open_threads']}")
        self.summaries = summaries
        return lines

    def _section_world_remembers(self) -> list[str]:
        lines = []
        location = self.location
        summaries = self.summaries
        full = self.full
        # --- The World Remembers (memory volunteered for THIS scene, never waited for) ---
        remembered, open_debts, held_back = self._world_remembers(
            location, full=full, already_shown=summaries)
        if remembered or open_debts:
            lines.append("")
            lines.append("--- THE WORLD REMEMBERS (older history this scene touches — "
                         "use it or let it lie, but don't contradict it) ---")
            for r in remembered:
                lines.append(f"- {self._truncate(r, 240, full)}")
            for d in open_debts:
                lines.append(f"OPEN DEBT: {d}")
            if held_back:
                rem = self._remainder(
                    held_back, "remembered entries", "--full or gm-recall.sh")
                if rem:
                    lines.append(rem)
        self.remembered = remembered
        return lines

    def _section_story_threads(self) -> list[str]:
        lines = []
        full = self.full
        # --- Story Threads (active plots, main first, each with its latest beat) ---
        all_threads = self._active_plot_threads(limit=None)
        threads = all_threads if full else all_threads[:6]
        if threads:
            lines.append("")
            lines.append("--- STORY THREADS ---")
            lines.extend(threads)
            rem = None if full else self._remainder(
                len(all_threads) - len(threads), "threads",
                "gm-plot.sh threads for all")
            if rem:
                lines.append(rem)
        return lines

    def _section_ready_threads(self) -> list[str]:
        lines = []
        location = self.location
        full = self.full
        # --- Ready Threads (dormant seeded plots that just became relevant) ---
        ready = self._ready_threads(location, full=full)
        if ready:
            lines.append("")
            lines.append("--- READY THREADS (dormant plots now relevant — wake with "
                         "gm-plot.sh update) ---")
            shown = ready if full else ready[:5]
            lines.extend(shown)
            rem = None if full else self._remainder(
                len(ready) - len(shown), "ready threads", "--full")
            if rem:
                lines.append(rem)
        return lines

    def _section_key_facts(self) -> list[str]:
        lines = []
        full = self.full
        # --- Key Facts (established plot facts the GM must keep continuity on) ---
        key_facts = self._key_facts(per_category=None if full else 3)
        if key_facts:
            lines.append("")
            lines.append("--- KEY FACTS ---")
            for fact_line in key_facts:
                lines.append(f"- {fact_line}")
            if not full:
                hidden_facts = len(self._key_facts(per_category=None)) - len(key_facts)
                rem = self._remainder(hidden_facts, "facts",
                                      "--full, or gm-note.sh recent / find")
                if rem:
                    lines.append(rem)
        return lines

    def _section_wrong_beliefs(self) -> list[str]:
        lines = []
        wrong = self._wrong_beliefs()
        if wrong:
            name = ((self.json_ops.load_json("character.json") or {}).get("identity") or {}).get(
                "name") or "The player character"
            lines.append("")
            lines.append(f"--- WHAT {name.upper()} GETS WRONG (narrate from the belief; "
                         f"the truth is for you) ---")
            lines += [f"- {w}" for w in wrong]
        return lines

    def _section_clocks(self) -> list[str]:
        lines = []
        # --- Threat Clocks (felt, mounting pressure; only when any are declared) ---
        clocks = self.json_ops.load_json("threat-clocks.json") or {}
        if clocks:
            lines.append("")
            lines.append("--- THREAT CLOCKS (most urgent first) ---")
            for clock_name, c in ThreatClockManager.by_urgency(clocks):
                cur, mx = int(c.get('current', 0)), int(c.get('max', 1))
                bar = "●" * cur + "○" * max(0, mx - cur)
                flag = "  ⚠ FULL — a beat is due" if cur >= mx else ""
                due = "" if flag else ThreatClockManager.due_text(c)
                about = f" — {c['text']}" if c.get('text') else ""
                lines.append(f"{clock_name}: [{bar}] {cur}/{mx}{due}{flag}{about}")
        return lines

    def _section_character(self) -> list[str]:
        lines = []
        full = self.full
        # --- Character ---
        lines.append("")
        lines.append("--- CHARACTER ---")
        # A damaged character.json stops the brief (JsonFileError), like any other
        # file: "No character found" would send the GM off to create a new one.
        char = self.json_ops.load_json("character.json") or None

        if char:
            import sheet as sheet_mod
            from body import summary as wound_summary
            from growth import growth_due, level, next_level_xp, xp_total
            identity = char.get('identity') or {}
            who = " ".join(x for x in (identity.get('race'), identity.get('role')) if x)
            conditions = sheet_mod.conditions(char)
            lines.append(f"{sheet_mod.name(char)}" + (f" ({who})" if who else "")
                         + f" - Level {level(char)} | Wounds: {wound_summary(char)}"
                         f" | XP: {xp_total(char)}/{next_level_xp(char)}"
                         f" | Credits: {sheet_mod.get(char, 'possessions', 'credits', 0)}")
            lines.append(f"Conditions: {', '.join(conditions) if conditions else '(none)'}")
            visible = sheet_mod.visible_items(char)
            if visible:
                lines.append(f"Gear (what others can see): {self._truncate(', '.join(visible), 200, full)}")
            due = growth_due(char)
            if due:
                lines.append(f"Growth due: {due} level{'s' if due != 1 else ''}, at the next quiet "
                             f"moment (rest, sleep, time alone): load gm-growth then. "
                             f"Never mention it to the player before.")
        else:
            lines.append("No character found.")
        self.char = char
        return lines

    def _section_party(self) -> list[str]:
        lines = []
        # --- Party Members ---
        npcs = self.json_ops.load_json("npcs.json") or {}
        party = [n for n, d in npcs.items() if isinstance(d, dict) and is_party_member(d)]
        lines.append("")
        lines.append("--- PARTY MEMBERS (with the player wherever they go) ---")
        lines.append(", ".join(party) if party else "(none)")
        self.npcs = npcs
        return lines

    def _section_people(self) -> list[str]:
        lines = []
        location = self.location
        summaries = self.summaries
        remembered = self.remembered
        char = self.char
        npcs = self.npcs
        full = self.full
        # --- People here (party and scene list): who they are, never mutated ---
        present = list(npcs_present(npcs, location, self._scene()))
        if present:
            lines.append("")
            lines.append("--- PEOPLE HERE (speak in their own voice; they know only what is "
                         "under 'they know') ---")
            fact_lists = self._npc_fact_lists(npcs, present,
                                              already_shown=list(summaries) + list(remembered))
            from note_manager import current_attitudes
            feelings = current_attitudes(self.json_ops.load_json("facts.json") or {})
            from sheet import name as sheet_name
            player_name = (sheet_name(char) if char else "") or "the player"
            for npc_name in present:
                person = self._person_lines(npc_name, npcs.get(npc_name) or {}, full)
                feeling = feelings.get((f"npc:{npc_name}", "player"))
                if feeling:                 # how they regard the player comes first
                    person.insert(1, f"  towards {player_name}: {feeling['fact']}")
                lines += person
                lists = fact_lists.get(npc_name, {})
                for key, label in (("know", "they know"), ("about", "about them")):
                    items = lists.get(key, [])
                    shown_items = items if full else items[-3:]
                    for text, old in shown_items:
                        tag = (" (old fact: who knows it isn't recorded)" if old
                               else ", they don't know" if key == "about" else "")
                        lines.append(f"  {label}{tag}: {self._truncate(text, 180, full)}")
                    if not full:
                        rem = self._remainder(len(items) - len(shown_items),
                                              f"facts {label}", "--full")
                        if rem:
                            lines.append(f"  {rem}")
        self.present = present
        return lines

    def _section_usual(self) -> list[str]:
        lines = []
        location = self.location
        npcs = self.npcs
        present = self.present
        # Where NPCs usually are is a hint, not presence (gm-scene.sh).
        present_names = set(present)
        usual = [n for n in npcs_usually_at(npcs, location) if n not in present_names]
        if usual:
            lines.append("")
            lines.append(f"Usually found here, not in the scene: {', '.join(usual)} "
                         f"(if one is actually here: bash tools/gm-scene.sh enter \"<name>\")")
        return lines

    def _section_pending(self) -> list[str]:
        lines = []
        full = self.full
        # --- Pending Consequences ---
        lines.append("")
        lines.append("--- PENDING CONSEQUENCES ---")
        consequences = self.json_ops.load_json("consequences.json") or {}
        pending = []
        if isinstance(consequences, dict):
            # Not-yet-resolved consequences live in the 'active' (and optional 'pending') lists
            for section in ('active', 'pending'):
                for cdata in consequences.get(section, []):
                    if not isinstance(cdata, dict):
                        continue
                    event = cdata.get('consequence', 'Unknown')
                    trigger = cdata.get('trigger', 'Unknown')
                    cid = str(cdata.get('id', '?'))
                    short_id = cid[:4] if len(cid) >= 4 else cid
                    typed = " · ".join(f"{t.get('type')} {t.get('match')}"
                                       for t in cdata.get('triggers') or []
                                       if isinstance(t, dict) and t.get('type'))
                    line = f"[{short_id}] {event} -> triggers: {trigger}"
                    line += f" [{typed}]" if typed else ""
                    then = describe_effects(cdata.get('effects'))
                    pending.append(line + (f" -> when it fires, {then}" if then else ""))
        elif isinstance(consequences, list):
            for cdata in consequences:
                if isinstance(cdata, dict):
                    event = cdata.get('consequence', cdata.get('event', 'Unknown'))
                    trigger = cdata.get('trigger', 'Unknown')
                    cid = str(cdata.get('id', '?'))
                    short_id = cid[:4] if len(cid) >= 4 else cid
                    pending.append(f"[{short_id}] {event} -> triggers: {trigger}")

        if pending:
            max_pending = len(pending) if full else 10
            for p in pending[:max_pending]:
                lines.append(p)
            if not full and len(pending) > max_pending:
                rem = self._remainder(
                    len(pending) - max_pending, "pending consequences",
                    "--full or gm-consequence.sh check")
                if rem:
                    lines.append(rem)
        else:
            lines.append("(none)")
        return lines

    def _section_world_rules(self) -> list[str]:
        lines = []
        campaign = self.campaign
        kit = self.kit
        # --- Your World's Rules (bespoke per-campaign systems; NEVER truncated) ---
        # Prefer kit signature_systems; campaign_rules is the legacy fallback.
        # These rules ARE the magic that makes each book feel distinct. The GM is
        # told to follow them exactly, so it must see them in full.
        systems = kit.signature_systems() if kit is not None else []
        if systems:
            lines.append("")
            lines.append("--- YOUR WORLD'S RULES (follow exactly) ---")
            for system in systems:
                name = system.get("name") or "unnamed"
                summary = system.get("summary") or ""
                extra = system.get("rules") or ""
                if summary:
                    lines.append(f"- {name}: {summary}")
                else:
                    lines.append(f"- {name}")
                if extra and extra != summary:
                    lines.append(f"    {extra}")
        else:
            rules = campaign.get('campaign_rules', {})
            if rules:
                import json
                lines.append("")
                lines.append("--- YOUR WORLD'S RULES (follow exactly) ---")
                if isinstance(rules, dict):
                    for key, val in rules.items():
                        if isinstance(val, (dict, list)):
                            lines.append(f"- {key}:")
                            for vline in json.dumps(val, indent=2, ensure_ascii=False).splitlines():
                                lines.append(f"    {vline}")
                        else:
                            lines.append(f"- {key}: {val}")
                elif isinstance(rules, list):
                    for rule in rules:
                        if isinstance(rule, (dict, list)):
                            for vline in json.dumps(rule, indent=2, ensure_ascii=False).splitlines():
                                lines.append(f"  {vline}")
                        else:
                            lines.append(f"- {rule}")
        return lines

    def _section_systems(self) -> list[str]:
        lines = []
        kit = self.kit
        # --- Signature Systems (executable primitives; the GM ROLLS these, not vibes) ---
        try:
            sys_list = kit.systems() if kit is not None else []
        except Exception:
            sys_list = []
        if sys_list:
            lines.append("")
            lines.append("--- YOUR WORLD'S SIGNATURE SYSTEMS (executable — ROLL these, "
                         "do not just narrate them) ---")
            counters = {v.lower(): v for v in kit.vitals() if v != "hp"}
            for s in sys_list:
                name = s.get('name', '')
                if s.get('primitive') == 'named_track' and name.lower() in counters:
                    how = f"counter: gm-player.sh vital {counters[name.lower()]} +1"
                elif s.get('primitive') == 'named_track':
                    how = "count it with an event clock: gm-clock.sh"
                else:
                    how = 'roll: uv run python lib/dice.py "1d20"'
                lines.append(f"- {name} ({how}): {self._system_summary(s)}")
        return lines

    # ==================== Private Helpers ====================

    def _system_summary(self, system):
        """One-line render of an instantiated signature system for the brief."""
        prim = system.get("primitive")
        cfg = system.get("config") or {}
        if prim == "named_track":
            mx = cfg.get("max", "?")
            ths = cfg.get("thresholds") or []
            parts = "; ".join(
                f"at {t.get('at')}: {t.get('consequence', '')}".strip()
                for t in ths if isinstance(t, dict))
            return f"track 0–{mx}" + (f" — {parts}" if parts else "")
        if prim == "price_roll":
            return "taking the marked action forces a cost roll"
        if prim == "reaction_roll":
            return "NPC opening reaction, modified by this world's reputation/track"
        if prim == "guarded_payoff":
            return "roll BEFORE taking marked treasure: clean / guardian wakes / curse attaches"
        return system.get("summary") or prim or ""

    def _recent_session_summaries(self, n=3):
        """Return recent completed-session summary paragraphs (oldest -> newest).

        Parses session-log.md blocks; a completed session is one with a
        '### Session Ended:' marker. n=None returns all.
        """
        log_path = self.campaign_dir / "session-log.md"
        if not log_path.exists():
            return []
        try:
            text = log_path.read_text(encoding='utf-8')
        except (OSError, ValueError):
            return []
        summaries = []
        for block in text.split("## Session Started:"):
            if "### Session Ended:" not in block:
                continue
            after = block.split("### Session Ended:", 1)[1]
            body = []
            for ln in after.splitlines()[1:]:  # skip the 'Session Ended' timestamp line
                if ln.strip() == "---":
                    break
                if ln.strip():
                    body.append(ln.strip())
            if body:
                summaries.append(" ".join(body))
        return summaries if n is None else summaries[-n:]

    def _cliffhanger(self, summary):
        """Best-effort 'where we paused' = last 1-2 sentences of a summary.

        Superseded by structured session metadata once session-identity-metadata lands.
        """
        normalized = summary.replace('!', '.').replace('?', '.')
        parts = [s.strip() for s in normalized.split('.') if s.strip()]
        return ('. '.join(parts[-2:]) + '.') if parts else ''

    def _ready_threads(self, location, full=False):
        """Dormant seeded plots that just became relevant — a nudge for the GM to wake them.

        A dormant plot surfaces here when (a) one of its linked NPCs is present, (b) its
        linked location is the current one, or (c) a threat clock linked to it is at
        least half full. Reuses `npcs_present` (the same presence predicate the NPC
        block and consequence tick use). Read-only; returns [] on any failure. This is
        what actively tells the GM a seeded thread is relevant NOW; `gm-plot.sh update`
        wakes it (dormant -> active).
        """
        try:
            plots = self.json_ops.load_json("plots.json") or {}
        except Exception:
            return []
        dormant = [(n, p) for n, p in plots.items()
                   if isinstance(p, dict) and p.get('status') == 'dormant']
        if not dormant:
            return []

        try:
            present = set(npcs_present(
                self.json_ops.load_json("npcs.json") or {}, location, self._scene()).keys())
        except Exception:
            present = set()

        # plot name -> a clock linked to it that is at least half full
        mature_clock = {}
        clocks = self.json_ops.load_json("threat-clocks.json") or {}
        if isinstance(clocks, dict):
            for cname, c in clocks.items():
                if not isinstance(c, dict):
                    continue
                lp, cur, mx = c.get('linked_plot'), c.get('current', 0), (c.get('max', 0) or 0)
                if lp and mx and cur >= mx / 2:
                    mature_clock[lp] = (cname, cur, mx)

        cur_loc = (location or '').strip().lower()
        out = []
        for name, p in dormant:
            npc_hit = next((n for n in (p.get('npcs') or []) if n in present), None)
            if npc_hit:
                reason = f"{npc_hit} is here"
            elif cur_loc and any((loc or '').strip().lower() == cur_loc
                                 for loc in (p.get('locations') or [])):
                reason = f"you are at {location}"
            elif name in mature_clock:
                cname, ccur, cmx = mature_clock[name]
                reason = f'the "{cname}" clock is {ccur}/{cmx}'
            else:
                continue
            hook = self._truncate(p.get('description', ''), 120, full)
            out.append(f'💤→ "{name}" — {hook} (because {reason})')
        return out

    def _active_plot_threads(self, limit=6):
        """Active plots, main-first, each with its latest event beat and its
        horizon: the people and places it names that have no record yet (named,
        not built until play walks there). limit=None = all."""
        from entity_aliases import resolve_entity_name
        plots = self.json_ops.load_json("plots.json") or {}
        if not isinstance(plots, dict):
            return []
        known = {"npcs": self.json_ops.load_json("npcs.json") or {},
                 "locations": self.json_ops.load_json("locations.json") or {}}
        closed = {'completed', 'resolved', 'failed', 'done', 'abandoned', 'dropped'}
        order = PLOT_TYPE_SORT
        active = []
        for name, p in plots.items():
            if not isinstance(p, dict):
                continue
            if str(p.get('status', 'active')).lower() in closed:
                continue
            if p.get('background'):
                continue  # import's background tier: real, but not a live thread
            ptype = str(p.get('type', 'side')).lower()
            # Within a type, order by spine `sequence` when present (arc order);
            # unsequenced plots sort last via a large fallback key.
            seq = p.get('sequence')
            seq = seq if isinstance(seq, int) else 9999
            latest = ''
            events = p.get('events')
            if isinstance(events, list) and events:
                ev = events[-1]
                latest = ev.get('event', ev.get('description', '')) if isinstance(ev, dict) else str(ev)
            horizon = [str(n) for field in ("npcs", "locations") for n in p.get(field) or []
                       if resolve_entity_name(str(n), known[field]) is None]
            active.append((order.get(ptype, len(order)), seq, ptype, name, latest, horizon))
        active.sort(key=lambda t: (t[0], t[1]))
        chosen = active if limit is None else active[:limit]
        return [f"[{ptype}] {name}" + (f" - latest: {latest}" if latest else "")
                + (f" · on the horizon (not built yet): {', '.join(horizon)}" if horizon else "")
                for _, _seq, ptype, name, latest, horizon in chosen]

    # Categories that carry continuity the GM must not contradict. `player_choices`
    # and `npc_relations` were advertised by gm-note.sh and read by nothing, so the
    # two categories that hold what the player DID were write-only. `session_events`
    # stays out (the session log and PREVIOUSLY ON own it) and so does `rules` (the
    # world's own rules block owns that); both remain reachable through recall.
    KEY_FACT_CATEGORIES = ('plot_local', 'plot_regional', 'plot_world',
                           'player_choices', 'npc_relations', 'lore')

    def _key_facts(self, per_category=3):
        """Established facts the GM must keep continuity on. per_category=None = all."""
        facts = self.json_ops.load_json("facts.json") or {}
        if not isinstance(facts, dict):
            return []
        out = []
        for cat in self.KEY_FACT_CATEGORIES:
            items = facts.get(cat)
            if not isinstance(items, list):
                continue
            chosen = items if per_category is None else items[-per_category:]
            for it in chosen:
                txt = fact_text(it)
                if txt:
                    out.append(txt)
        return out

    def _wrong_beliefs(self):
        """Lines for what the player character holds that is wrong or partial,
        each with the truth beside it, so the GM narrates from the belief."""
        facts = self.json_ops.load_json("facts.json") or {}
        entries = [f for items in facts.values() if isinstance(items, list)
                   for f in items if isinstance(f, dict)]
        by_id = {f.get('id'): f for f in entries}
        out = []
        for f in entries:
            if 'player' not in (f.get('holders') or []) or f.get('truth') not in ('wrong', 'partial'):
                continue
            kind = "believes" if f['truth'] == 'wrong' else "knows only part"
            line = f"{f.get('id')} ({kind}): {f.get('fact', '')}"
            true = by_id.get(f.get('version_of'))
            if true:
                line += f"  → truth, {true.get('id')}: {true.get('fact', '')}"
            out.append(line)
        return out

    def _world_remembers(self, location, full=False, already_shown=()):
        """What the campaign's long-term memory volunteers for THIS scene.

        CampaignMemory (arcs, session history, facts — embedded and searchable)
        had no automated reader: recall fired only when the GM thought to ask,
        which requires already suspecting there is something to remember. That is
        the exact failure memory exists to fix. The scene itself is the query —
        where we are, and who is standing here.

        Returns (entries, open_debts, held_back_total). Degrades to empty on any
        failure — no memory file, no embedding deps, a half-written index — so a
        broken memory costs the brief nothing mid-session.
        """
        try:
            from campaign_memory import CampaignMemory
            mem = CampaignMemory(self._wsd)
            npcs = self.json_ops.load_json("npcs.json") or {}
            present = list(npcs_present(npcs, location, self._scene()))
            query = " ".join([location or ""] + present).strip()
            if not query:
                return [], [], 0
            top_k = None if full else 3
            hits = mem.recall(query, top_k=top_k)
            arcs = mem.arcs()
            debts = [str(d) for d in (arcs[-1].get("open_debts") or [])] if arcs else []
            total = len(mem.entries())
        except Exception:
            return [], [], 0

        # Don't echo PREVIOUSLY ON. recall() falls back to re-gathering the session
        # log, so its top hits are frequently the very summaries printed above —
        # compare on collapsed whitespace, and either way round, since a gathered
        # entry may span several logged sessions.
        def _norm(s):
            return " ".join(str(s).split())

        shown = [_norm(s) for s in already_shown if _norm(s)]
        entries = []
        for h in hits:
            text = str(h.get("text", "")).strip()
            norm = _norm(text)
            if not norm or any(norm in s or s in norm for s in shown):
                continue
            shown.append(norm)
            entries.append(text)
        held_back = total - len(entries) if (entries and not full and total > len(entries)) else 0
        return entries, debts, held_back

    def _person_lines(self, name, npc, full=False):
        """An NPC in the brief: who they are and how to play them, from their sheet
        (sheet.py). Only the fields that are filled in."""
        import sheet as sheet_mod
        identity = npc.get('identity') or {}
        personality = npc.get('personality') or {}
        status = npc.get('status') or {}
        who = identity.get('role') or self._truncate(identity.get('background') or '', 100, full)
        head = [x for x in (who,
                            f"Big Five {personality['big_five']}" if personality.get('big_five') else "",
                            personality.get('demeanor')) if x]
        lines = [f"{name}" + (f" ({'; '.join(head)})" if head else "") + ":"]
        look = sheet_mod.look_line(npc)
        if look:
            lines.append(f"  look: {self._truncate(look, 160, full)}")
        for label, value in (("voice", personality.get('voice')),
                             ("tells", personality.get('tells')),
                             ("wants", personality.get('want')),
                             ("after now", status.get('goal')),
                             ("fears", personality.get('fears'))):
            if value:
                lines.append(f"  {label}: {self._truncate(value, 160, full)}")
        if full:
            for label, value in (("needs", personality.get('need')),
                                 ("values", personality.get('values')),
                                 ("affiliation", identity.get('affiliation'))):
                if value:
                    lines.append(f"  {label}: {value}")
        visible = sheet_mod.visible_items(npc)
        if visible:
            lines.append(f"  gear: {self._truncate(', '.join(visible), 160, full)}")
        if status.get('conditions'):
            lines.append(f"  conditions: {', '.join(status['conditions'])}")
        return lines

    def _npc_fact_lists(self, npcs, names, already_shown=()):
        """For each NPC name: {"know": [...], "about": [...]}, facts as (text, old).

        "know": facts with the NPC among their `holders`. "about": facts about
        the NPC (`about`) that they don't hold: secrets about them, talk behind
        their back. A fact from before holders existed (no `holders` field) can't
        say who knows it; it goes under "about" with old=True when its `about`,
        or failing that the name check gm-note.sh uses, finds the NPC. Facts
        already shown (PREVIOUSLY ON, the world remembers) or identical to one of
        the NPC's own `events` are left out. Oldest first; [] on any failure.
        """
        out = {n: {"know": [], "about": []} for n in names}
        facts = self.json_ops.load_json("facts.json") or {}
        if not isinstance(facts, dict) or not names:
            return out
        from world_ids import WorldIds
        ids = WorldIds(self.json_ops)

        def norm(text):
            return " ".join(str(text).split())

        shown = {norm(x) for x in already_shown if norm(x)}
        entries = sorted((f for items in facts.values() if isinstance(items, list)
                          for f in items if isinstance(f, dict) and f.get('fact')),
                         key=lambda f: str(f.get('timestamp', '')))
        for f in entries:
            if f.get('attitude'):
                continue                    # shown as the person's "towards" line
            text = fact_text(f)
            if norm(f['fact']) in shown or norm(text) in shown:
                continue
            old = 'holders' not in f
            about = f.get('about')
            if about is None and old:
                about = ids.mentioned(str(f["fact"]))
            for name in names:
                nid = f"npc:{name}"
                if not old and nid in f['holders']:
                    out[name]["know"].append((text, False))
                elif nid in (about or []):
                    out[name]["about"].append((text, old))
        return out
