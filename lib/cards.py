#!/usr/bin/env python3
"""Scene cards: what the GM needs about a place or a person, when it comes into play.

The commands that change the scene print them, so the GM never has to ask:
`gm-session.sh move` prints the site card (from another site) or the location's
own lines (within one: lib/sites.py), `gm-scene.sh enter` an NPC card
for each person who enters, and `gm-scene.sh` alone the whole scene. The brief
shows the scene the same way.

A card shows what the record says about its subject, then a few facts, those that
fit the scene best first (recall.SceneRanker: by meaning when semantic recall is
installed, else by the place, the people present and recency):

    site card       the description and exits; presence; who is usually found in
                    it (and in which location); the plots that involve it or one of
                    its locations; the facts that fit the scene anywhere in it, those
                    the character knows and those they don't
    location lines  a location in a site on its own: its description, and its own
                    exits (a laid-out site); after a move within the site, all
                    that is printed
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
# Nothing on a card is cut: a fact shortened can drop its turn, and the GM can't
# tell. A fact is printed in full or named by id.


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
            location = self._here()
        if location not in self._rankers:
            from recall import SceneRanker
            present = npcs_present(self.npcs, self._here(), self.overview.get("scene"))
            self._rankers[location] = SceneRanker(self.json_ops, location, present)
        return self._rankers[location]

    def _is_shown(self, fact: dict) -> bool:
        return (bool(fact.get("id")) and fact["id"] in self.shown) \
            or _norm(fact_text(fact)) in self.shown_texts or _norm(fact["fact"]) in self.shown_texts

    def _fact_list(self, label: str, facts: list, hint: str, tag=None,
                   hidden_is_given: bool = False, location: str = None,
                   name_shown: bool = True) -> list[str]:
        """Up to PER_LIST facts under `label`, those that fit the scene best first
        (recall.SceneRanker), not counting those printed already: with `name_shown`
        (a person's lists: who knows it is news) a better-fitting one printed above
        is named by id. Then how many more there are, and the command that lists them. `hidden_is_given`: the
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
        if again and name_shown:
            lines.append(f"  {label}: also {', '.join(again)} (above)")
        rest = len(facts) - len(fresh) - len(again)
        if rest > 0:
            lines.append(f"  +{rest} more ({hint})")
        return lines

    # ---------- the location card ----------

    def _here(self) -> str:
        pos = self.overview.get("player_position") or {}
        return pos.get("current_location", "") if isinstance(pos, dict) else ""

    def location_card(self, location: str, plots: bool = True) -> list[str]:
        """The place as the GM needs it on arriving from another site: the site card,
        then, for a location in the site, its own lines (location_lines)."""
        import sites
        lines = self.site_card(sites.site_of(location), plots=plots)
        if sites.in_site(location):
            lines += self.location_lines(location)
        return lines

    def location_lines(self, location: str) -> list[str]:
        """A place on its own, as on a move within its site: "<name>: <description>",
        and the exits of a location that has its own (a site's layout: site-architect)."""
        import sites
        from session_manager import SessionManager
        place = self.locations.get(location)
        name = sites.own_name(location)
        if not isinstance(place, dict):
            return [f"{name}: (not recorded)"]
        description = str(place.get("description") or "").strip()
        lines = [f"{name}: {description}" if description else
                 f"{name}: (no description yet: write one before narrating the place, "
                 f"bash tools/gm-location.sh describe \"{location}\" \"...\")"]
        exits, _ = SessionManager._normalize_connection_list(place.get("connections", []))
        if exits and sites.in_site(location):
            lines.append("  Exits: " + "; ".join(
                f"{sites.own_name(c['to']) if sites.same_site(c['to'], location) else c['to']}"
                + (f" ({c['path']})" if c.get("path") else "") for c in exits))
        import world_rules
        if sites.in_site(location):
            lines += [f"  Rule here: {line}" for line in
                      world_rules.holder_lines(self.json_ops, f"location:{location}")]
        return lines

    def _usual_line(self, site: str) -> list[str]:
        """Who is usually found in the site and isn't in the scene, each with their
        location in it where one is given."""
        import sites
        present = set(npcs_present(self.npcs, self._here(), self.overview.get("scene")))
        usual = []
        for n, data in npcs_usually_at(self.npcs, site).items():
            if n in present:
                continue
            inside = [sites.own_name(p) for p in (data.get("places") or {}).get("usual") or []
                      if sites.in_site(p) and sites.same_site(p, site)]
            usual.append(n + (f" ({', '.join(inside)})" if inside else ""))
        return [f"Usually found here, not in the scene: {', '.join(usual)} "
                f"(if one is actually here: bash tools/gm-scene.sh enter \"<name>\")"] if usual else []

    def site_card(self, site: str, plots: bool = True) -> list[str]:
        """A site as recorded: its description and exits, presence, who is usually
        found in it (with their location), (with `plots`) the open plots that involve
        it or one of its locations; then the facts that fit the scene best, those the
        character knows and those they don't, a fact anywhere in the site counting
        as the site's (sites.py)."""
        from session_manager import SessionManager
        place = self.locations.get(site)
        lines = []
        if isinstance(place, dict):
            description = str(place.get("description") or "").strip()
            lines.append(f"{site}: {description}" if description else
                         f"{site}: (no description yet: write one before narrating the place, "
                         f"bash tools/gm-location.sh describe \"{site}\" \"...\")")
            exits, _ = SessionManager._normalize_connection_list(place.get("connections", []))
            if exits:
                lines.append("Exits: " + "; ".join(
                    f"{c['to']} ({c['path']})" if c.get("path") else c["to"] for c in exits))
            lines += self._presence_line(site)
        else:
            lines.append(f"{site or '(no location)'}: (not recorded)")
        lines += self._usual_line(site)
        if plots:
            lines += self._plots_of(f"location:{site}", "Plots here")
        import world_rules
        lines += [f"Rule here: {line}" for line in world_rules.holder_lines(self.json_ops, f"location:{site}")]
        # Not only the facts of the place: whatever fits the scene best, the site's
        # own facts helped by the bonuses (docs/modules/campaign-memory.md). Split by
        # who knows it, so the GM sees at once what the character can draw on.
        known, hidden = [], []
        for f in self.facts:
            if f.get("attitude") or fact_file.unheard(f):
                continue
            if {"player", "public"} & set(f.get("holders") or []):
                known.append(f)
            else:
                hidden.append(f)
        like = 'gm-note.sh find --like "<what is happening>"'
        # A place only ranks its facts: one printed above says nothing more here.
        lines += self._fact_list("fits here", known, f'{like} --held-by player --at "{site}"',
                                 location=site, name_shown=False)
        lines += self._fact_list(f"fits here, {self.player} doesn't know", hidden,
                                 f'{like} --hidden --at "{site}"', hidden_is_given=True,
                                 location=site, name_shown=False)
        return lines

    def _plots_of(self, cid: str, label: str) -> list[str]:
        """The open plots that involve `cid`, most pressing first, one line each."""
        from plot_manager import plot_name, plot_order
        plots = self.json_ops.load_json("plots.json") or {}
        import sites
        keys = [k for k in plot_order(self.json_ops, plots)
                if any(i == cid or (cid.startswith("location:") and i.startswith("location:")
                                    and sites.at(i, cid)) for i in plots[k].get("involves") or [])]
        return [f"{label}: {plot_name(self.json_ops, k, plots[k])}: "
                f"{plots[k].get('stands') or plots[k].get('goal', '')}"
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
        lines += self._faction_lines(npc)
        lines += ["  " + line for line in self._plots_of(nid, "in plot")]
        import world_rules
        lines += [f"  rule: {line}" for line in world_rules.holder_lines(self.json_ops, nid)]
        from factions import knowers
        mine = knowers(nid, self.npcs)            # they know what their factions know
        knows, wrong, about, shared = [], [], [], 0
        for f in self.facts:
            if f.get("attitude") or fact_file.unheard(f):
                continue
            holders = f.get("holders") or []
            if mine & set(holders) or "public" in holders:  # public: known to everyone, them too
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
            "about them, they don't know", about, f"gm-note.sh find --about \"{nid}\"")
        if shared:
            lines.append(f"  + {shared} fact{'s' if shared != 1 else ''} they share with "
                         f"{self.player} (gm-note.sh find --held-by \"{nid}\" --held-by player)")
        return lines

    def _faction_lines(self, npc: dict[str, Any]) -> list[str]:
        """'member of: Lull Corporation; the Coven (SECRET: …)'."""
        from factions import known, memberships
        table = known(self.json_ops)
        parts = [table.get(m["id"], {}).get("name", m["id"])
                 + (" (SECRET: only its members know; nobody else acts on it)" if m.get("secret")
                    else "") for m in memberships(npc)]
        return [f"  member of: {'; '.join(parts)}"] if parts else []

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
                             ("goal", status.get("goal")),
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

    def scene(self, plots: bool = True) -> list[str]:
        """The place and the time, the location card, then a card for everyone present."""
        location = self._here()
        moment = current_time(self.json_ops)
        when = ""
        if moment:
            from time_manager import derive_time_of_day
            when = f", {moment:%H:%M} ({derive_time_of_day(moment)})"
        lines = [f"SCENE: {location or '(no location)'}{when}"]
        lines += self.location_card(location, plots=plots)
        present = npcs_present(self.npcs, location, self.overview.get("scene"))
        for name in present:
            lines += [""] + self.npc_card(name)
        for fid, why in self.factions_here(location, present):
            lines += [""] + self.faction_card(fid, why)
        return lines

    # ---------- the faction card ----------

    def _presence_line(self, location: str) -> list[str]:
        """'Presence: The Kin 4, Red Fork Police 2; not here: Hardtop Holdings (0)'."""
        from factions import known, presence
        here = presence(self.json_ops, location)
        if not here:
            return []
        names = known(self.json_ops)
        name = lambda f: names.get(f, {}).get("name", f)    # noqa: E731
        there = [f"{name(f)} {n}" for f, n in here.items() if n > 0]
        absent = [name(f) for f, n in here.items() if n == 0]
        return ["Presence (0–5): " + ", ".join(there or ["none written above 0"])
                + (f"; not here: {', '.join(absent)}" if absent else "")]

    def factions_here(self, location: str, present) -> list[tuple[str, str]]:
        """(faction id, why it is here) for each faction present at this place
        (presence 1 or more, its site's), with a member in the scene, or with an
        open plot involving the place's site or one of its locations; most present
        first."""
        import sites
        from factions import load, members, presence
        from plot_manager import plot_order
        plots = self.json_ops.load_json("plots.json") or {}
        lid = f"location:{location}"
        strength = presence(self.json_ops, location)
        out = []
        for fid in load(self.json_ops):
            here = [(k, s) for k, s in members(self.npcs, fid) if k in present]
            tied = [k for k in plot_order(self.json_ops, plots)
                    if any(i.startswith("location:") and sites.same_site(i, lid)
                           for i in plots[k].get("involves") or [])
                    and f"faction:{fid}" in [plots[k].get("owner"), *(plots[k].get("involves") or [])]]
            why = [f"presence here: {strength[fid]}"] if strength.get(fid) else []
            if here:
                why.append("members here: " + ", ".join(
                    k + (" (SECRET member: only its members know)" if s else "") for k, s in here))
            if tied:
                why.append(f"tied to this place by: {', '.join(tied)}")
            if why:
                out.append((fid, "; ".join(why)))
        return sorted(out, key=lambda x: -strength.get(x[0], 0))

    def faction_card(self, fid: str, why: str) -> list[str]:
        """How to play a faction: what it is, what drives it, what it never does,
        its plots (in full above) and its rule values. What it knows is on its
        members' cards."""
        import world_rules
        from factions import _dead_mark, load
        from plot_manager import plot_order
        row = load(self.json_ops)[fid]
        kind = f"; {row['kind']}" if row.get("kind") else ""
        lines = [f"FACTION {row['name']} (faction:{fid}{kind}): {row.get('description', '')}",
                 f"  {why}"]
        for field in ("impulses", "values"):
            if row.get(field):
                lines.append(f"  {field}: " + " / ".join(row[field]))
        for field in ("leader", "successor"):
            if row.get(field):
                lines.append(f"  {field}: {row[field].partition(':')[2]}{_dead_mark(self.json_ops, row[field])}")
        plots = self.json_ops.load_json("plots.json") or {}
        owned = [k for k in plot_order(self.json_ops, plots) if plots[k].get("owner") == f"faction:{fid}"]
        if owned:
            lines.append(f"  wants (its plots, above): {', '.join(owned)}")
        import faction_rules
        lines += [f"  {line}" for line in faction_rules.card_lines(self.json_ops, fid)]
        lines += [f"  rule: {line}" for line in world_rules.holder_lines(self.json_ops, f"faction:{fid}")]
        return lines


def main() -> int:
    """`cards.py location [<place>]` | `cards.py npc <name>...` | `cards.py scene`.
    `location` alone is the card after a move: after a move within one site only
    the place's own lines (Cards.location_lines)."""
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
        import sites
        pos = cards.overview.get("player_position") or {}
        before = pos.get("previous_location", "") if isinstance(pos, dict) else ""
        here = " ".join(args[1:]) or cards._here()
        within = not args[1:] and sites.same_site(before, here) and before.lower() != here.lower()
        print("\n".join(cards.location_lines(here) if within else cards.location_card(here)))
    elif action == "npc" and args[1:]:
        blocks = [cards.npc_card(name) for name in args[1:]]
        print("\n\n".join("\n".join(b) for b in blocks))
    else:
        print("Usage: cards.py scene | location [<place>] | npc <name>...", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
