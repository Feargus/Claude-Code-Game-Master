#!/usr/bin/env python3
"""Scene cards: what the GM needs about a place or a person, when it comes into play.

The commands that change the scene print them, so the GM never has to ask:
`gm-session.sh move` prints the location card, `gm-scene.sh enter` an NPC card
for each person who enters, and `gm-scene.sh` alone the whole scene. The brief
shows the scene the same way.

A card shows what the record says about its subject, then a few facts, those that
fit the scene best first (recall.SceneRanker: by meaning when semantic recall is
installed, else by the place, the people present and recency):

    location card   the description and exits; who is usually found there; the
                    consequences waiting there and the plots that involve it; the facts
                    that fit the scene, those the character knows and those they don't
    NPC card        the sheet: who they are and how to play them; their
                    attitudes (towards the player first); what they know that
                    the player doesn't; what they believe that is wrong or only
                    part of the truth; what is true about them that they don't
                    know; and only a count of the other facts they share with the
                    player, who was told them already

Within one command's output a fact is printed once; a later card names it by id.
"""

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

import facts as fact_file
import sheet as sheet_mod
from entity_manager import npcs_present, npcs_usually_at
from game_time import current_time
from note_manager import current_attitudes, fact_text

PER_LIST = 3          # facts per list on a card; revisit once semantic recall ranks them
# Nothing on a card is cut (2026-11-15): a fact shortened can drop its turn, and the
# GM can't tell. A fact is printed in full or named by id. To revisit (todo.md).


def _norm(text: str) -> str:
    return " ".join(str(text).split())


class Cards:
    """Cards for one campaign. Keeps track of the facts it has printed, so one
    command's cards print each fact once. `shown_texts` are texts printed before
    the cards (the brief's earlier sections), left out the same way."""

    def __init__(self, json_ops, shown_ids=(), shown_texts=()):
        self.json_ops = json_ops
        self.shown = set(shown_ids)
        self.shown_texts = {_norm(t) for t in shown_texts if _norm(t)}
        facts = fact_file.load(json_ops)
        self.facts = fact_file.newest_first([f for f in facts if f.get("fact")])
        self.attitudes = current_attitudes(facts)
        self.npcs = json_ops.load_json("npcs.json") or {}
        self.locations = json_ops.load_json("locations.json") or {}
        self.overview = json_ops.load_json("campaign-overview.json") or {}
        self.player = sheet_mod.name(json_ops.load_json("character.json") or {}) or "the character"
        self._ids = None
        self._rankers = {}

    # ---------- helpers ----------

    def _world_ids(self):
        if self._ids is None:
            from world_ids import WorldIds
            self._ids = WorldIds(self.json_ops)
        return self._ids

    def _ranker(self, location: str = None):
        """The scene's ranking (recall.SceneRanker): the given place, or the current
        one, and the people in the scene."""
        if location is None:
            pos = self.overview.get("player_position") or {}
            location = pos.get("current_location", "") if isinstance(pos, dict) else ""
        if location not in self._rankers:
            from recall import SceneRanker
            present = npcs_present(self.npcs, location, self.overview.get("scene"))
            self._rankers[location] = SceneRanker(self.json_ops, location, present)
        return self._rankers[location]

    def _is_shown(self, fact: dict) -> bool:
        return (bool(fact.get("id")) and fact["id"] in self.shown) \
            or _norm(fact_text(fact)) in self.shown_texts or _norm(fact["fact"]) in self.shown_texts

    def _fact_list(self, label: str, facts: list, hint: str, tag=None,
                   hidden_is_given: bool = False, location: str = None) -> list[str]:
        """Up to PER_LIST facts under `label`, those that fit the scene best first
        (recall.SceneRanker), not counting those printed already: a better-fitting
        one printed above is named by id. Then how many
        more there are, and the command that lists them. `hidden_is_given`: the
        label says the player doesn't know them, so the [HIDDEN FROM PLAYER] mark
        is left out."""
        if not facts:
            return []
        facts = self._ranker(location).rank(facts)
        lines, again, fresh = [], [], []
        for f in facts:                     # the best not printed yet; better ones printed are named
            if len(fresh) == PER_LIST:
                break
            if self._is_shown(f) and f.get("id"):   # one without an id can't be named
                again.append(f["id"])
            else:
                fresh.append(f)
        for f in fresh:
            if f.get("id"):
                self.shown.add(f["id"])
            extra = tag(f) if tag else ""
            text = fact_text(f, self.player)
            if hidden_is_given:
                text = text.replace("[HIDDEN FROM PLAYER] ", "", 1)
            fid = f"{f['id']} " if f.get("id") else ""
            lines.append(f"  {label}{extra}: {fid}{text}")
        if again:
            lines.append(f"  {label}: also {', '.join(again)} (above)")
        rest = len(facts) - len(fresh) - len(again)
        if rest > 0:
            lines.append(f"  +{rest} more ({hint})")
        return lines

    # ---------- the location card ----------

    def location_card(self, location: str, waiting: bool = True) -> list[str]:
        """The place as recorded: description, exits, who is usually here, and
        (with `waiting`) what waits here, then the facts that fit the scene best:
        those the character knows, and those they don't."""
        from session_manager import SessionManager
        place = self.locations.get(location)
        moment = current_time(self.json_ops)
        when = ""
        if moment:
            from time_manager import derive_time_of_day
            when = f", {moment:%H:%M} ({derive_time_of_day(moment)})"
        lines = [f"SCENE: {location or '(no location)'}{when}"]
        if isinstance(place, dict):
            description = str(place.get("description") or "").strip()
            lines.append(f"Here: {description}" if description else
                         f"Here: (no description yet: write one before narrating the place, "
                         f"bash tools/gm-location.sh describe \"{location}\" \"...\")")
            exits, _ = SessionManager._normalize_connection_list(place.get("connections", []))
            if exits:
                lines.append("Exits: " + "; ".join(
                    f"{c['to']} ({c['path']})" if c.get("path") else c["to"] for c in exits))
        present = set(npcs_present(self.npcs, location, self.overview.get("scene")))
        usual = [n for n in npcs_usually_at(self.npcs, location) if n not in present]
        if usual:
            lines.append(f"Usually found here, not in the scene: {', '.join(usual)} "
                         f"(if one is actually here: bash tools/gm-scene.sh enter \"<name>\")")
        if waiting:
            lines += self._waiting_here(location)
        # Not only the facts of the place: whatever fits the scene best, the place's
        # own facts helped by the bonuses (recall-proposal.md, decision 4). Split by
        # who knows it, so the GM sees at once what the character can draw on.
        lid = f"location:{location}"
        known, hidden = [], []
        for f in self.facts:
            if f.get("attitude"):
                continue
            holders = f.get("holders")
            if holders is None:                   # an old fact: only if it is the place's
                if f.get("at") == lid or lid in (f.get("about") or []):
                    known.append(f)
            elif {"player", "public"} & set(holders):
                known.append(f)
            else:
                hidden.append(f)
        like = 'gm-note.sh find --like "<what is happening>"'
        lines += self._fact_list("fits here", known, f'{like} --held-by player --at "{location}"',
                                 location=location)
        lines += self._fact_list(f"fits here, {self.player} doesn't know", hidden,
                                 f'{like} --hidden --at "{location}"', hidden_is_given=True,
                                 location=location)
        return lines

    def _waiting_here(self, location: str) -> list[str]:
        """Consequences that fire at this place, and the open plots that involve it."""
        lines = []
        lid = f"location:{location}".lower()
        store = self.json_ops.load_json("consequences.json") or {}
        for c in store.get("active", []) if isinstance(store, dict) else []:
            if any(isinstance(t, dict) and t.get("type") == "on_location"
                   and str(t.get("match", "")).lower() == lid for t in c.get("triggers") or []):
                lines.append(f"Waiting here: [{str(c.get('id', '?'))[:4]}] "
                             f"{c.get('consequence', '')}")
        lines += self._plots_of(f"location:{location}", "Plots here")
        return lines

    def _plots_of(self, cid: str, label: str) -> list[str]:
        """The open plots that involve `cid`, most pressing first, one line each."""
        from plot_manager import plot_order
        plots = self.json_ops.load_json("plots.json") or {}
        keys = [k for k in plot_order(self.json_ops, plots) if cid in (plots[k].get("involves") or [])]
        return [f"{label}: [{plots[k].get('kind', '?')}] {k}: "
                f"{plots[k].get('stands') or plots[k].get('description', '')}"
                for k in keys]

    # ---------- the NPC card ----------

    def npc_card(self, name: str) -> list[str]:
        """Who they are, how they regard others, and what they know or don't."""
        npc = self.npcs.get(name) or {}
        lines = self._person(name, npc)
        nid = f"npc:{name}"
        mine = [(whom, f) for (holder, whom), f in self.attitudes.items() if holder == nid]
        mine.sort(key=lambda pair: pair[0] != "player")             # the player first
        lines[1:1] = [f"  towards {self.player if whom == 'player' else whom.partition(':')[2]}: "
                      f"{f['fact']}" for whom, f in mine]           # right under who they are
        lines += ["  " + line for line in self._plots_of(nid, "in plot")]
        knows, wrong, about, shared = [], [], [], 0
        for f in self.facts:
            if f.get("attitude"):
                continue
            holders = f.get("holders")
            if holders is None:                       # before holders were recorded
                if nid in (f.get("about") or self._world_ids().mentioned(str(f["fact"]))):
                    about.append(f)
                continue
            if nid in holders:
                if f.get("truth") in ("wrong", "partial"):
                    wrong.append(f)                   # play them from the belief
                elif {"player", "public"} & set(holders):
                    shared += 1
                else:
                    knows.append(f)
            elif nid in (f.get("about") or []):
                about.append(f)
        lines += self._fact_list(f"knows, and {self.player} doesn't", knows,
                                 f"gm-note.sh find --held-by \"{nid}\" --hidden",
                                 hidden_is_given=True)
        lines += self._fact_list("believes, wrongly or in part", wrong,
                                 f"gm-note.sh find --held-by \"{nid}\" --truth wrong")
        lines += self._fact_list(
            "about them, they don't know", about, f"gm-note.sh find --about \"{nid}\"",
            tag=lambda f: " (old fact: who knows it isn't recorded)" if "holders" not in f else "")
        if shared:
            lines.append(f"  + {shared} fact{'s' if shared != 1 else ''} they share with "
                         f"{self.player} (gm-note.sh find --held-by \"{nid}\" --held-by player)")
        return lines

    def _person(self, name: str, npc: dict[str, Any]) -> list[str]:
        """The sheet: who they are and how to play them. Only fields that are filled in."""
        identity = npc.get("identity") or {}
        personality = npc.get("personality") or {}
        status = npc.get("status") or {}
        who = identity.get("role") or identity.get("background") or ""
        head = [x for x in (who,
                            f"Big Five {personality['big_five']}" if personality.get("big_five") else "",
                            personality.get("demeanor")) if x]
        lines = [f"{name}" + (f" ({'; '.join(head)})" if head else "") + ":"]
        look = sheet_mod.look_line(npc)
        if look:
            lines.append(f"  look: {look}")
        for label, value in (("voice", personality.get("voice")),
                             ("tells", personality.get("tells")),
                             ("wants", personality.get("want")),
                             ("after now", status.get("goal")),
                             ("fears", personality.get("fears"))):
            if value:
                lines.append(f"  {label}: {value}")
        for label, value in (("needs", personality.get("need")),
                             ("values", personality.get("values")),
                             ("affiliation", identity.get("affiliation"))):
            if value:
                lines.append(f"  {label}: {value}")
        if not look and not personality:
            lines.append("  only a sketch: give them a look and a voice before playing them "
                         "(gm-npc.sh set ...)")
        visible = sheet_mod.visible_items(npc)
        if visible:
            lines.append(f"  gear: {', '.join(visible)}")
        if status.get("conditions"):
            lines.append(f"  conditions: {', '.join(status['conditions'])}")
        return lines

    # ---------- the whole scene ----------

    def scene(self, waiting: bool = True) -> list[str]:
        """The location card, then a card for everyone present."""
        pos = self.overview.get("player_position") or {}
        location = pos.get("current_location", "") if isinstance(pos, dict) else ""
        lines = self.location_card(location, waiting=waiting)
        for name in npcs_present(self.npcs, location, self.overview.get("scene")):
            lines += [""] + self.npc_card(name)
        return lines


def main() -> int:
    """`cards.py location [<place>]` | `cards.py npc <name>...` | `cards.py scene`."""
    from campaign_manager import CampaignManager
    from json_ops import JsonOperations
    args = sys.argv[1:]
    campaign = CampaignManager().get_active_campaign_dir()
    if campaign is None:
        print("[ERROR] No active campaign.", file=sys.stderr)
        return 1
    cards = Cards(JsonOperations(str(campaign)))
    action = args[0] if args else "scene"
    if action == "scene":
        print("\n".join(cards.scene()))
    elif action == "location":
        pos = cards.overview.get("player_position") or {}
        here = " ".join(args[1:]) or (pos.get("current_location", "") if isinstance(pos, dict) else "")
        print("\n".join(cards.location_card(here)))
    elif action == "npc" and args[1:]:
        blocks = [cards.npc_card(name) for name in args[1:]]
        print("\n\n".join("\n".join(b) for b in blocks))
    else:
        print("Usage: cards.py scene | location [<place>] | npc <name>...", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
