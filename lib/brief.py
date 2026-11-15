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
from entity_manager import is_party_member
from note_manager import fact_text
from threat_clocks import ThreatClockManager
from world_kit import WorldKit


class Brief:
    """The brief for one campaign, built from a SessionManager's view of it."""

    # The sections in the order they are printed: each is a method
    # `_section_<name>` returning its lines ([] when it has nothing to show).
    SECTIONS = ("header", "kit", "play_style", "images", "voice",
                "plots", "key_facts", "wrong_beliefs", "clocks", "character", "party", "scene",
                "pending", "world_rules", "systems")

    def __init__(self, session):
        self.session = session
        self.json_ops = session.json_ops
        self.campaign_dir = session.campaign_dir
        self.campaign_file = session.campaign_file
        self.character_file = session.character_file
        self._wsd = session._wsd

    # What the brief asks of the session (kept there: moves use them too).
    def get_preferences(self) -> dict[str, Any]:
        return self.session.get_preferences()

    def _scene(self):
        return self.session._scene()

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

    def get_full_context(self, full: bool = False) -> str:
        """The whole brief: each section in turn. Some sections leave what they
        loaded or showed for later ones (the location, the character, the
        session summaries already printed)."""
        self.full = full
        self.shown_texts = []       # facts printed so far, so the cards don't repeat them
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
        world = self.json_ops.load_json("world-bible.json") or {}
        campaign_name = world.get('name') or campaign.get('name') or campaign.get('campaign_name') or 'Unknown Campaign'
        location = campaign.get('player_position', {}).get('current_location', 'Unknown')
        time_of_day = campaign.get('time', {}).get('time_of_day', campaign.get('time_of_day', ''))
        current_date = campaign.get('time', {}).get('current_date', campaign.get('current_date', ''))
        game_time = campaign.get('game_time') or ''
        if len(game_time) >= 16:
            time_of_day = f"{time_of_day} ({game_time[11:16]})"
        time_str = f"{time_of_day}, {current_date}" if time_of_day and current_date else time_of_day or current_date or 'Unknown'

        lines.append("=== SESSION CONTEXT ===")
        lines.append(f"Campaign: {campaign_name}")
        lines.append(f"Location: {location} | Time: {time_str}")
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

    def _section_plots(self) -> list[str]:
        """Every open plot, most pressing first (plot_manager.plot_order): where it
        stands, whose goal it is, and who and what in it is still a sketch."""
        from opening import Opening
        from plot_manager import plot_order
        plots = self.json_ops.load_json("plots.json") or {}
        keys = plot_order(self.json_ops, plots)
        if not keys:
            return []
        horizon = Opening(self._wsd).horizon
        lines = ["", "--- PLOTS (most pressing first; gm-plot.sh show \"<plot>\" for one in full) ---"]
        for key in keys:
            p = plots[key]
            lines.append(f"[{p.get('kind', '?')}] {key}: "
                         + self._truncate(p.get('stands') or p.get('description', ''), 240, self.full))
            if p.get("owner"):
                owner = p["owner"].partition(":")[2] or p["owner"]
                lines.append(f"  {owner} wants: {p.get('goal') or '(no goal written)'}")
            sketches = horizon(key)
            if sketches:
                lines.append(f"  still sketches (named, not built): {', '.join(sketches)}")
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

    def _section_scene(self) -> list[str]:
        """The scene as cards (lib/cards.py): the place, then everyone present.
        Facts printed in an earlier section are not printed again. What waits
        at the place is left to READY THREADS and PENDING CONSEQUENCES."""
        from cards import Cards
        cards = Cards(self.json_ops, full=self.full, shown_texts=self.shown_texts)
        return ["", "--- THE SCENE (play the people as their cards say; they know only "
                    "what is on their card or shared with the player) ---"] + cards.scene(waiting=False)

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

    # Categories that carry continuity the GM must not contradict. `player_choices`
    # and `npc_relations` were advertised by gm-note.sh and read by nothing, so the
    # two categories that hold what the player DID were write-only. `session_events`
    # stays out (the plots carry what happened) and so does `rules` (the world's
    # own rules block owns that); both remain reachable through recall.
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
        if per_category is not None or self.full:
            self.shown_texts = getattr(self, "shown_texts", []) + out
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
            self.shown_texts = getattr(self, "shown_texts", []) + [f.get('fact', '')]
        return out
