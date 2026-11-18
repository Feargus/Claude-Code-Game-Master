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

import facts as fact_file
from consequence_manager import describe_effects
from entity_manager import is_party_member
from note_manager import fact_text
from threat_clocks import ThreatClockManager
from world_kit import WorldKit


class Brief:
    """The brief for one campaign, built from a SessionManager's view of it."""

    # The sections in the order they are printed: each is a method
    # `_section_<name>` returning its lines ([] when it has nothing to show).
    # Ordered by plot (2026-11-15): each open plot with its clocks, the
    # consequences waiting in it and what the character doesn't know of it; then
    # what belongs to no plot; the character; the world; the scene; then the
    # newest facts not shown above, so the cards don't repeat them.
    SECTIONS = ("header", "kit", "play_style", "images", "plots", "unplotted",
                "character", "party", "wrong_beliefs", "world_rules", "voice",
                "scene", "latest")
    SECRETS_PER_PLOT = 5     # what the character doesn't know, newest first
    LATEST = 5               # the newest facts not shown above

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

    @staticmethod
    def _normalize_connection_list(connections):
        from session_manager import SessionManager
        return SessionManager._normalize_connection_list(connections)

    def text(self) -> str:
        return self.get_full_context()

    @staticmethod
    def _truncate(text: str, limit: int) -> str:
        """Trim long text."""
        if not text or len(text) <= limit:
            return text
        return text[:limit - 3].rstrip() + "..."

    @staticmethod
    def _remainder(hidden: int, noun: str, hint: str) -> str | None:
        """Disclosure line for a truncated list: '+N more <noun> — <hint>'."""
        if hidden <= 0:
            return None
        return f"+{hidden} more {noun} — {hint}"

    def get_full_context(self) -> str:
        """The whole brief: each section in turn. Some sections leave what they
        loaded or showed for later ones (the location, the character, the facts
        already printed)."""
        self.shown_texts = []       # facts printed so far, so the cards don't repeat them
        self.shown_ids = set()
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
            lines.append("")
            lines.append("--- KIT ---")
            lines.append(f"name: {kit.name()}")
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
            for p in passages[:3]:
                lines.append(f"  | {p}")
        self.bible = bible
        return lines

    def _section_plots(self) -> list[str]:
        """Every open plot, most pressing first (plot_manager.plot_order): where it
        stands, whose goal it is, who and what in it is still a sketch, its
        clocks, the consequences waiting in it, and what the character doesn't
        know of it (secrets and facts only others hold), newest first."""
        from opening import Opening
        from plot_manager import plot_order
        plots = self.json_ops.load_json("plots.json") or {}
        self.open_plots = keys = plot_order(self.json_ops, plots)
        if not keys:
            return []
        horizon = Opening(self._wsd).horizon
        lines = ["", "--- PLOTS (most pressing first; gm-plot.sh show \"<plot>\" for one in full) ---"]
        for key in keys:
            p = plots[key]
            lines.append(f"[{p.get('kind', '?')}] {key}: {p.get('stands') or p.get('description', '')}")
            if p.get("owner"):
                owner = p["owner"].partition(":")[2] or p["owner"]
                lines.append(f"  {owner} wants: {p.get('goal') or '(no goal written)'}")
            sketches = horizon(key)
            if sketches:
                lines.append(f"  still sketches (named, not built): {', '.join(sketches)}")
            lines += self._belongings(lambda plots_of, k=key: k in plots_of,
                                      f'gm-note.sh find --plot "{key}" --hidden')
        return lines

    def _section_unplotted(self) -> list[str]:
        """Clocks, waiting consequences and what the character doesn't know that
        belong to no open plot."""
        open_plots = set(getattr(self, "open_plots", []))
        body = self._belongings(lambda plots_of: not open_plots & set(plots_of),
                                "gm-note.sh find --hidden", unplotted=True)
        return ["", "--- IN NO PLOT ---"] + body if body else []

    def _belongings(self, belongs, more_hint: str, unplotted: bool = False) -> list[str]:
        """The lines under one plot: its clocks, its waiting consequences, and
        what the character doesn't know of it, what fits the scene first.
        `belongs(plots)` says whether a record with that `plots` list is in it."""
        lines = []
        clocks = {n: c for n, c in (self.json_ops.load_json("threat-clocks.json") or {}).items()
                  if isinstance(c, dict) and belongs(c.get("plots") or [])}
        for name, c in ThreatClockManager.by_urgency(clocks):
            cur, mx = int(c.get('current', 0)), int(c.get('max', 1))
            state = "FULL: a beat is due" if cur >= mx else (
                f"{cur}/{mx}" + ThreatClockManager.due_text(c))
            lines.append(f"  clock {name}: {state}" + (f" ({c['text']})" if c.get('text') else ""))
        waiting = [c for c in self._open_consequences() if belongs(c.get("plots") or [])]
        for c in waiting:
            cid = str(c.get('id', '?'))[:4]
            if c.get("fired"):       # it happened: to be played out, then resolved
                lines.append(f"  FIRED, not resolved yet [{cid}]: {c.get('consequence', '?')} "
                             f"(because: {c['fired'].get('reason', '?')})")
                continue
            then = describe_effects(c.get('effects'))
            lines.append(f"  waiting [{cid}]: {c.get('consequence', '?')} "
                         f"(when: {self._when(c)})" + (f"; when it fires, {then}" if then else ""))
        unknown = self._scene().rank([f for f in self._facts_newest_first()
                                      if self._unknown_to_character(f)
                                      and belongs(f.get("plots") or [])])
        if unknown:
            lines.append(f"  {self._character_name()} doesn't know:")
            for f in unknown[:self.SECRETS_PER_PLOT]:
                lines.append(f"    {self._fact_line(f)}")
            if len(unknown) > self.SECRETS_PER_PLOT:
                lines.append(f"    + {len(unknown) - self.SECRETS_PER_PLOT} more: {more_hint}")
        return lines

    def _section_latest(self) -> list[str]:
        """What just happened, for picking up where play stopped: the newest facts
        not printed above. The newer ones that were are named by id first, so the
        order stays readable."""
        facts = [f for f in self._facts_newest_first() if not f.get("attitude")]
        fresh = [f for f in facts if f.get("id") not in self.shown_ids][:self.LATEST]
        if not fresh:
            return []
        newer = [f["id"] for f in facts if f.get("id") in self.shown_ids
                 and self._number(f) > self._number(fresh[0])]
        from note_manager import NARROW
        lines = ["", "--- LATEST (the newest facts not shown above) ---"]
        if newer:
            lines.append(f"  newer, above: {', '.join(newer)}")
        lines += [f"  {self._fact_line(f)}" for f in fresh]
        return lines + [f"  more: {NARROW}"]

    # ---------- what the plot sections read ----------

    def _facts_newest_first(self) -> list[dict]:
        return fact_file.newest_first(fact_file.load(self.json_ops))

    _number = staticmethod(fact_file.number)

    @staticmethod
    def _unknown_to_character(f: dict) -> bool:
        """A secret, or a fact only others hold; attitudes are on the cards, and
        the character's wrong beliefs have their own section."""
        holders = f.get("holders")
        return (isinstance(holders, list) and not {"player", "public"} & set(holders)
                and not f.get("attitude"))

    def _fact_line(self, f: dict) -> str:
        """`fN <text>` with who knows it when only others do; marks it printed."""
        self.shown_ids.add(f.get("id"))
        self.shown_texts.append(f.get("fact", ""))
        text = fact_text(f, self._character_name()).replace("[HIDDEN FROM PLAYER] ", "")
        holders = f.get("holders")
        if self._unknown_to_character(f) and holders:
            names = [h.partition(":")[2] or ("the street" if h == "street" else h) for h in holders]
            text += f" ({', '.join(names)} {'knows' if len(names) == 1 else 'know'})"
        return f"{f.get('id')} {text}"

    def _scene(self):
        """The scene's ranking (recall.SceneRanker): the current place and the people
        in the scene. Those that fit best come first."""
        if getattr(self, "_scene_ranker", None) is None:
            from entity_manager import npcs_present
            from recall import SceneRanker
            overview = self.json_ops.load_json(self.campaign_file) or {}
            pos = overview.get("player_position") or {}
            location = pos.get("current_location", "") if isinstance(pos, dict) else ""
            npcs = self.json_ops.load_json("npcs.json") or {}
            self._scene_ranker = SceneRanker(self.json_ops, location,
                                             npcs_present(npcs, location, overview.get("scene")))
        return self._scene_ranker

    def _character_name(self) -> str:
        import sheet as sheet_mod
        return sheet_mod.name(self.json_ops.load_json("character.json") or {}) or "The character"

    @staticmethod
    def _when(c: dict) -> str:
        """A consequence's trigger in words, and how it fires when that says more
        (`on_location location:Floor 2 Junction`); not when it only repeats it."""
        said = str(c.get('trigger') or '').strip()
        typed = [t for t in c.get('triggers') or [] if isinstance(t, dict) and t.get('type')]
        repeats = len(typed) == 1 and said in (str(typed[0].get('match')),
                                               str(typed[0].get('match')).partition(':')[2])
        how = " · ".join(f"{t['type']} {t.get('match')}" for t in typed)
        if how and not repeats:
            return f"{said}; {how}" if said else how
        return said or how or "?"

    def _open_consequences(self) -> list[dict]:
        store = self.json_ops.load_json("consequences.json") or {}
        if isinstance(store, list):
            return [c for c in store if isinstance(c, dict)]
        return [c for section in ("active", "pending") for c in store.get(section) or []
                if isinstance(c, dict)]

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

    def _section_character(self) -> list[str]:
        lines = []
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
                lines.append(f"Gear (what others can see): {self._truncate(', '.join(visible), 200)}")
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
        lines.append(f"--- PARTY MEMBERS (with {self._character_name()} wherever they go) ---")
        lines.append(", ".join(party) if party else "(none)")
        self.npcs = npcs
        return lines

    def _section_scene(self) -> list[str]:
        """The scene as cards (lib/cards.py): the place, then everyone present.
        Facts printed in an earlier section are named by id. What waits at the
        place is under its plot above."""
        from cards import Cards
        cards = Cards(self.json_ops, shown_ids=self.shown_ids, shown_texts=self.shown_texts)
        lines = cards.scene(waiting=False)
        self.shown_ids |= cards.shown                  # LATEST leaves out what the cards printed
        return (["", "--- THE SCENE (play the people as their cards say; they know only "
                     f"what is on their card or shared with {self._character_name()}) ---"]
                + lines)

    def _section_world_rules(self) -> list[str]:
        """The campaign's own rules in full (world_rules.py), never cut: the GM is
        told to follow them exactly, so it must see them whole."""
        import world_rules
        rules = world_rules.brief_lines(self.json_ops)
        if not rules:
            return []
        return ["", "--- YOUR WORLD'S RULES (follow exactly) ---"] + rules

    # ==================== Private Helpers ====================

    def _wrong_beliefs(self):
        """Lines for what the player character holds that is wrong or partial,
        each with the truth beside it, so the GM narrates from the belief."""
        entries = fact_file.load(self.json_ops)
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
