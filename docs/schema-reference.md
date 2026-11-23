# World State JSON Schema Reference

*Claude, 2026-11-19: kept in step with the code since 2026-11; the npcs.json and plots.json sections are known to be stale.*

The on-disk shape of a campaign, which no single source file declares — the managers each
write their own slice. **`lib/schemas.py` is the authority on every enum below**; where
this document lists allowed values it is a convenience copy, and the copy has drifted
before. Re-derive with `uv run python lib/schemas.py` (validates the active campaign) or by
reading the `VALID_*` / `PLOT_TYPE*` sets at the top of that file.

---

## Campaign Structure

Each campaign lives in its own folder: `world-state/campaigns/<name>/`. The active campaign
is named in `world-state/active-campaign.txt`.

```
<campaign-name>/
├── campaign-overview.json   # Campaign settings, player position
├── character.json           # Player character sheet (FLAT shape)
├── npcs.json                # All NPCs
├── locations.json           # All locations
├── factions.json            # Factions, by id (factions.py, gm-faction.sh)
├── facts.json               # World facts, one list
├── removed-facts.json       # Facts the GM removed (gm-note.sh remove), with when
├── plots.json               # Plot hooks and quests
├── items.json               # Items (from imports)
├── consequences.json        # Pending/resolved events + firing provenance
├── ruleset.json             # The world's own rules (gm-rule.sh define)
├── rule-state.json          # Where the world's own rules stand, per holder (world_rules.py)
├── rules.log                # Every change of those values
├── world-bible.json         # Fidelity spine (voice, glossary, geography)
├── session-log.md           # Session history — the canonical ledger
├── threat-clocks.json       # Named pressure clocks (optional)
├── embeddings.npz           # Vectors for recall by meaning; derived (embedding_store.py)
├── world-tick-log.json      # Between-session tick provenance
├── loremaster-cache.json    # Per-location grounded briefs
├── saves/                   # Snapshot saves
├── fallen/                  # Archived sheets of dead PCs
├── chunks/ · vectors/       # the book's pieces (chunks.json) and their vectors (book.npz)
└── extracted/               # Legacy census-import staging
```

Most of these are created lazily — a campaign that was never imported has no `vectors/`.

---

## campaign-overview.json

```json
{
  "campaign_name": "string",
  "current_date": "string (in-game date)",
  "time_of_day": "dawn|morning|midday|afternoon|dusk|evening|night|midnight",
  "player_position": {
    "current_location": "string or null",
    "previous_location": "string or null",
    "arrival_time": "ISO timestamp"
  },
  "scene": {"location": "the location this list belongs to",
            "present": ["NPC keys in the scene besides the party (gm-scene.sh)"]},
  "current_character": "string (character name)",
  "session_count": 0,

  "story_spine": {"arc": ["ordered plot names"], "through_line": "string"},
  "preferences": {"action_menu": true, "rag_inspiration": false},
  "scene": {"location": "string", "present": ["NPC keys in the scene"]},
  "opened": "YYYY-MM-DDTHH:MM (when gm-session.sh opening set up the first scene)"
}
```

The world's own rules are not here: they are `ruleset.json`'s (see below). Worlds are
free to add their own keys here (the shipped DCC fixture carries `viewer_stats`, `pending_boxes`, and
`pending_interview_topics`).

**The opening leaves no record of its own** except `opened`: `gm-session.sh opening`
(`lib/opening.py`) writes the first scene into the ordinary files (places, NPCs, the
scene list, a plot, facts, clocks). It replaced the stored `play_pack` and
`opening_hook` (2026-11-08), which went stale. See [the dream](conventions/the-dream.md).

---

## npcs.json

A dictionary keyed by NPC name.

```json
{
  "NPC_NAME": {
    "description": "string (physical/personality description)",
    "attitude": "ally|neutral|enemy|friendly|hostile|suspicious|helpful",
    "created": "ISO timestamp",
    "events": [
      {"event": "string describing what happened", "timestamp": "ISO timestamp"}
    ],
    "tags": {
      "locations": ["location name"],
      "quests": ["quest name"]
    },
    "context": ["canonical voice lines — verbatim source dialogue"],
    "enhanced": false,
    "enhanced_at": "ISO timestamp",
    "background": true,
    "is_party_member": false,
    "became_pc": false,
    "character_sheet": null,

    "aliases": ["name variants recorded by the integrity gate"],
    "visual_appearance": {"sex": "", "age": "", "race": "", "species": "", "hair": "",
                          "face": "", "eyes": "", "clothing": "", "gear": "",
                          "demeanor": "", "size": ""},
    "goal": "string", "current_mood": "neutral",
    "voice": "string — how they SOUND (not their lines; those are `context`)",
    "bonds": {},
    "stats": {"ac": null, "hp": 45, "cr": 3, "difficulty": "minion|standard|boss",
              "statless": false}
  }
}
```

Notes:

- **`context` vs `voice`** are routinely confused — `context` holds quotable lines;
  `voice` describes the sound. See [NPC model](modules/npc-model.md).
- **`tags.locations` is the only location field** (since 2026-08-13). A campaign imported
  earlier may still carry a legacy `location_tags` — migrate with
  `gm-npc.sh unify-tags`. See the tag-split gotcha.
- **`background: true` is the import's entity tier** (`extraction_cap`), present on
  npcs, locations, items and plots alike. It marks everything the importance ranking
  put below the top-N — a real entity the book named, kept whole on disk, just not part
  of the playable core. Absent means active; the key is omitted rather than set false.
  It changes three things: `gm-enhance.sh batch` skips these entities (a RAG round-trip
  each); `gm-npc.sh promote` clears the flag, because a party member is active by
  definition; and a background **plot** is left out of the scene context's STORY THREADS
  and of `gm-plot.sh threads`, which discloses how many it held back. It does **not**
  gate an NPC's presence in a scene — that is decided by `tags.locations` against the
  party's location, for background and active NPCs alike.

`attitude` values above are the `VALID_ATTITUDES` set in `lib/schemas.py`; an invalid
attitude is coerced to `neutral` on batch import rather than rejected.

### Party Member Character Sheet

When `is_party_member: true`, the `character_sheet` contains:

```json
{
  "character_sheet": {
    "race": "Human",
    "class": "Fighter",
    "level": 2,
    "hp": {
      "current": 18,
      "max": 22
    },
    "ac": 14,
    "stats": {"str": 14, "dex": 12, "con": 13, "int": 10, "wis": 11, "cha": 10},
    "saves": {"str": 4, "dex": 1, "con": 3, "int": 0, "wis": 0, "cha": 0},
    "skills": {},
    "attack_bonus": 4,
    "damage": "1d8+2",
    "equipment": ["Longsword", "Shield", "Chain Shirt"],
    "features": ["Second Wind", "Fighting Style (Defense)"],
    "conditions": [],
    "xp": 0
  }
}
```

**HP Tracking:** Party members use `hp.current` and `hp.max`. Update with:
```bash
bash tools/gm-npc.sh hp "Name" -5   # Damage
bash tools/gm-npc.sh hp "Name" +3   # Heal
```

### Field Descriptions

| Field | Required | Description |
|-------|----------|-------------|
| description | Yes | Character description |
| attitude | Yes | One of the supported attitude values |
| created | Yes | ISO timestamp when created |
| tags | No | Object with `locations` and `quests` arrays |
| events | No | Array of event objects |
| context | No | Source passages for RAG enhancements |
| enhanced | No | Flag when RAG enhancements applied |
| enhanced_at | No | ISO timestamp when enhanced |
| is_party_member | No | True if NPC is a party member |
| character_sheet | No | Full character sheet if party member (see above)

---

## locations.json

A dictionary keyed by location name.

```json
{
  "LOCATION_NAME": {
    "position": "string (relative position, e.g. 'north of town')",
    "description": "string (what the place looks like)",
    "connections": [
      {"to": "Other Location", "path": "rocky trail"}
    ],
    "discovered": "ISO timestamp",
    "presence": {"<faction id>": 4, "<another>": 0},
    "notes": "optional string",
    "source": "optional string",
    "background": true,
    "low_confidence": true
  }
}
```

Notes:

- **`presence`**: how much each faction is around here, 0 (known not to be there: an
  enemy's headquarters) to 5 (they run it); a faction not listed was never written
  (`gm-location.sh presence`, `lib/factions.py`). A faction present (1 or more) gets a
  card in the scene; at 4 or 5 a fact recorded here says "they have eyes here", a hint
  for `gm-note.sh tell`, never automatic.
- **`low_confidence: true` marks a reconcile stub** (`location_reconcile`): the source
  referenced this place from a plot, an NPC tag, or a connection, but no extractor
  produced a node for it, so the import created one and wired it to the most-connected
  hub. The flag says the name is the book's and everything else is a guess — flesh it
  out in play. These nodes also carry `source: "auto-stub"` and a `notes` line saying so.
- **`background: true`** on a location is the same entity tier described under
  [npcs.json](#npcsjson).

### Dungeon Rooms (Extended Schema)

Dungeon rooms (stored in `locations.json`) may include:

```json
{
  "ROOM_NAME": {
    "dungeon": "string (dungeon name)",
    "room_number": 1,
    "description": "string",
    "exits": {
      "north": {"to": "Room 2", "type": "open|door|secret|stairs-up|stairs-down"}
    },
    "state": {"discovered": false, "visited": false, "cleared": false}
  }
}
```

---

## facts.json

One list of fact **objects**, in the order they were recorded (`lib/facts.py`: every
script reads and writes the file through it). `gm-note.sh edit` gives a fact a new text;
`gm-note.sh remove` moves one to `removed-facts.json`, with a `removed` timestamp, so its
id is never given again; a fact something still points at (a version of it, a waiting
consequence that tells it, an NPC's death) can't be removed.

```json
[
  {"id": "f1", "fact": "The kingdom has been at peace for 100 years",
   "game_time": "2187-10-23T04:30", "timestamp": "2026-01-28T21:50:30Z"},
  {"id": "f2", "fact": "The party met the king on day 1", "about": ["npc:King Harald"],
   "holders": ["player", "npc:King Harald"], "timestamp": "..."}
]
```

- `id`: `f1`, `f2`, … counted up, so other records can point to a fact and the list is in
  id order.
- `game_time`: the in-game time when the fact was recorded, copied from
  `campaign-overview.json`. Missing on facts from before it existed.
- `timestamp`: the real-world time it was recorded.
- `about` (optional): ids of who or what the fact concerns (see below). `gm-note.sh` adds
  the ids given with `--about` and every name it finds in the text (whole names or NPC
  `aliases`, first letter a capital; `--not-about` drops one); an unknown id refuses the
  fact. `gm-note.sh about <fact id> --add/--remove <id>` changes it later. Facts written
  before 2026-11-06 have none yet.
- `holders`: ids of who knows the fact: `player`, `npc:<key>`, `street`, `public` (a place
  can't be one). `gm-note.sh` defaults to the player plus the NPCs present (the party and
  the scene list, `gm-scene.sh`; never the dead); `--also` adds to that, `--holders` replaces it,
  `--secret` stores `[]`. Off-screen facts from the world tick default to `[]`. `[]` means
  nobody knows: a GM-only secret. A missing field (facts from before 2026-11-06) means not
  recorded. `gm-note.sh tell <fact id> <holder>...` adds holders.
- `truth` (optional): missing means true; `"partial"` is true but leaves things out;
  `"wrong"` is plain wrong. `version_of` (optional): the id of the fullest true version
  (needs a `truth`). A version of a version is stored as pointing at its root, so the
  truth is one step away; a wrong fact with no truth behind it can't be pointed at.
  `fact_text()` (`lib/note_manager.py`) marks such text `[WRONG; the truth is fN]` /
  `[PARTIAL; fuller: fN]`, a fact nobody holds (`holders: []`) `[SECRET]`, and one
  that others hold but not the player (nor `public`) `[HIDDEN FROM PLAYER]`, in the brief, the NPC lists, long-term memory and search; the
  brief lists what the player holds wrongly or partly next to the truth.
  `gm-note.sh … --truth --version-of` sets them at recording, `gm-note.sh truth <id>
  wrong|partial|true [--version-of <id> | --no-version]` later.

**Ids for what a fact is about or held by** (`lib/world_ids.py`, for `about` and the coming
`holders`): `player`, `npc:<key>`, `location:<key>`, `faction:<id>`, and the rungs `street` and
`public`. The stored id is the exact key (`npc:Auntie Ro`, `faction:lull`); input may differ in case,
punctuation, titles or use an alias (a faction is also found by its name), and the player character's name resolves to `player`.
Unknown ids are refused with close matches. Item ids come with items that have ids.
`python lib/world_ids.py list` prints every id; `check <id>…` tests some.

Managers write the object form.

Categories are provisional; nothing depends on their names any more (KEY FACTS and the
keyword recall that read them are gone). Recall by meaning: [recall](modules/campaign-memory.md).

### Common Categories

- `world_building` - Established world facts
- `session_events` - What happened this session
- `plot_local` - Local storyline facts
- `plot_regional` - Broader mystery/conspiracy facts
- `plot_world` - World-shaking revelations
- `player_choices` - Key decisions made
- `npc_relations` - How NPCs feel about the party
- `dropped_references` - Import provenance: place references `location_reconcile` could
  not turn into a node (a connection's routing rule, or a blank). Written by the import,
  not by play — it exists so a discarded name is recoverable instead of stdout-only.

---

## consequences.json

Tracks events that will trigger in the future.

```json
{
  "active": [
    {
      "id": "8-char-uuid",
      "consequence": "string (what will happen)",
      "trigger": "string (free-text, when it triggers)",
      "created": "ISO timestamp",

      "triggers": [   (OPTIONAL, structured; any one fires it)
        {"type": "on_location | on_npc | on_time | on_death | on_clock | on_learn | on_fact",
         "match": "on_location: location:<key>; on_npc: npc:<key>; on_death: npc:<key> or player;
                   on_time: a time-of-day word (its hours); on_clock: <clock>:<segment>;
                   on_learn: <who> learns <fact id> | <who> learns about:<id>; on_fact: the fact it waits for, in words"}
      ],
      "effects": [   (OPTIONAL, carried out by the script each time it fires)
        {"type": "start_clock", "name": "clock name", "segments": 3, "on": "time | event",
         "due_in": "3d (counted from the firing)  | or due: YYYY-MM-DD HH:MM",
         "consequence": "what happens when the clock fills (optional)"},
        {"type": "tell", "fact": "f42", "holders": ["npc:Wren", "street"]}
      ]
    }
  ],
  "resolved": [
    {
      "id": "8-char-uuid",
      "consequence": "string",
      "trigger": "string",
      "created": "ISO timestamp",
      "resolved": "ISO timestamp",
      "expired": "ISO timestamp (when aged out rather than resolved)"
    }
  ],

  "provenance": [
    {"id": "…", "consequence": "…", "reason": "why it matched", "fired_at": "ISO timestamp"}
  ]
}
```

`on_death` is an **event trigger**: its `match` is an NPC's key in `npcs.json` (resolved
when the consequence is added) or `player`, and it fires only inside `gm-npc.sh kill` /
`gm-player.sh kill`, never on the scene check. `gm-consequence.sh fire <id>` fires any
consequence by hand; `--by <fact id>` records the fact that fulfilled it (`fact` in its
provenance entry). `on_fact` is an event trigger too, matched by the GM: its `match` is
the awaited event in words, and every fact recorded with `gm-note.sh` lists the
consequences waiting on one. `on_clock` is an event trigger whose `match` is
`"<clock name>:<segment>"` (a bare clock name is stored as its last segment, i.e. full); the
clock must exist. It fires inside `gm-clock.sh advance` and the time update that moves the
clock, once for each segment the clock reaches. It may also name a clock that a waiting
consequence's `start_clock` effect will create.

`on_learn` is an event trigger whose `match` is `"<who> learns <fact id>"` or
`"<who> learns about:<id>"` (stored canonical; input may say `about <id>` and use loose
names). `<who>` is a holder id (`player`, `npc:<key>`, `street`, `public`) or `anyone`. It
fires inside every command that adds a holder to a fact: `gm-note.sh` recording a fact (its
first holders learn it), `gm-note.sh tell`, and world-tick developments with holders. A
consequence fires once per learning however many of its triggers fit; it can fire again on
a later learning until it is resolved.

A `start_clock` effect runs however the consequence fires (scene check, event, or by hand),
after `consequences.json` is saved; a clock of that name that already exists is left as it
is. The fired consequence comes back with `effects_done` (what happened, in words; not
saved).

A `tell` effect (`--tells <fact id> --to <holder>`, checked when added) adds holders to
the fact through `gm-note.sh tell`'s own path, so their `on_learn` consequences fire too
and are listed in `effects_done`. Someone who already knows learns nothing, which is what
ends a chain.
Both `kill` commands also record the death as a fact. A dead NPC carries `status: "dead"`, `cause`, `died_at` and
`died_game_time`.

A fired consequence carries `fired` (`reason`, `at`, `game_time`, and `fact` when a fact
set it off) and stays in `active` until it is resolved; it matches no trigger any more.
`gm-consequence.sh rearm` removes `fired`. See [the living world](modules/living-world.md).

**Structured triggers** (`triggers`) are additive and
optional. Entries written before 2026-11-06 store a single trigger as top-level
`trigger_type` + `match` instead of a `triggers` list; they are read as a one-item list.
Entries with only the free-text `trigger` are read as an `on_fact` trigger with that
text, and `add` stores a bare free-text trigger that way. There is no word matching.

---

## plots.json

A dictionary keyed by plot name.

`type` comes from the single canonical taxonomy, `schemas.PLOT_TYPES` — derived from
`schemas.PLOT_TYPE_SORT`, whose ranks are also the display/sort order for STORY THREADS
and plot listings. `validators`, `minor_stubs`, `plot_manager` and `session_manager` all
import it; there is no second copy. `minor_stubs.validate_plot_types` (the `/import`
validate step) passes canonical types through untouched, maps extractor synonyms
(`quest`→`side`, `arc`→`main`, `conflict`→`threat`, …) via `PLOT_TYPE_SYNONYMS`, and only
falls back to `side` — with a warning naming the original — for a type it does not know.

```json
{
  "PLOT_NAME": {
    "type": "main|threat|mystery|side|personal|world|optional|scene|theme|idea|lore|background|other",
    "status": "active|completed|failed|dormant|available",
    "sequence": 1,
    "depends_on": ["earlier plot name"],
    "description": "string (what the quest is about)",
    "npcs": ["involved", "npc", "names"],
    "locations": ["relevant", "locations"],
    "objectives": ["optional objective strings"],
    "rewards": "optional string",
    "consequences": "optional string",
    "events": [
      {"event": "progress update", "timestamp": "ISO timestamp"}
    ],
    "completed_at": "ISO timestamp or null",
    "failed_at": "ISO timestamp or null"
  }
}
```

---

## items.json

A dictionary keyed by item name. Typically populated by `/import`.

```json
{
  "ITEM_NAME": {
    "name": "string",
    "description": "string",
    "type": "weapon|armor|potion|scroll|wondrous|treasure|equipment|prop|artifact",
    "rarity": "common|uncommon|rare|very rare|legendary|artifact",
    "mechanics": "optional string",
    "value": "optional string",
    "location": "optional string",
    "attunement": false,
    "cursed": false,
    "source": "optional string"
  }
}
```

---

## character.json

The player character sheet, in the **flat** canonical shape. `stats` is an open,
kit-defined dict — the six abilities below are a D&D example, not a requirement. A legacy
open-schema file (`identity`/`vitals`/`attributes`) is migrated to flat on first read.
See [the player character sheet](modules/player-character.md).

```json
{
  "name": "string",
  "race": "string",
  "class": "string",
  "level": 1,
  "background": "string",

  "stats": {
    "str": 10,
    "dex": 10,
    "con": 10,
    "int": 10,
    "wis": 10,
    "cha": 10
  },

  "hp": {"current": 10, "max": 10},

  "ac": 10,
  "skills": {},
  "saves": {"str": 0, "dex": 0, "con": 0, "int": 0, "wis": 0, "cha": 0},

  "equipment": ["item", "names"],
  "features": ["class", "features"],
  "background": "string",
  "alignment": "string",
  "bonds": "string",
  "flaws": "string",
  "ideals": "string",
  "traits": "string",
  "notes": [],
  "credits": 20,
  "xp": {"current": 0, "next_level": 300},

  "conditions": [],
  "status": "alive | dying | dead",
  "died_at": "ISO timestamp (set by gm-player.sh kill)",
  "cause": "string",
  "visual_appearance": {"…11 fixed fields — see lib/visual_appearance.py"},
  "current_location": "string",
  "id": "string"
}
```

`xp` accepts a bare integer and is normalized to `{current, next_level}` on load. The
world's own rules (Bleed, a sea level) are not on the sheet: their values are in
`rule-state.json`.

---

## Save Files (saves/*.json)

A named point-in-time copy of **live campaign state**, not of derived indexes.
`SessionManager.create_save` writes `{YYYYMMDD-HHMMSS}-{name}.json` under `saves/`;
a same-second collision uniquifies the filename instead of overwriting.

**Versioned (`save_version: 1`).** Snapshot keys are campaign filenames plus the
`characters` helper (the PC sheet, keyed `character`) and `fallen/<file>.json`.
JSON values are objects; markdown values are strings. A file that is not on disk
is omitted — never stubbed as `{}`. Restore writes only keys the snapshot has.

Skipped (derived, staging, or the save dir itself): `chunks/`, `vectors/`,
`extracted/`, `canon/`, `authored/`, `loremaster-cache.json`, `saves/`.

Combat lives in `combat_state.json` (the file `CombatManager` actually writes).

**Autosaves.** A save whose name is `autosave` (the Stop hook) keeps the newest
`AUTOSAVE_KEEP` (3) matching files; named manual saves are not rotated.
`_find_save("autosave")` returns the newest remaining autosave.

**Legacy (no `save_version`).** Snapshot used underscored keys covering six files
(`campaign_overview`, `npcs`, `locations`, `facts`, `consequences`, `characters`).
Restore still applies those six, then prints a partial-restore warning naming
contract files the snapshot did not include. Present-time plots, clocks, and
items otherwise stay mixed in — do not treat a legacy save as a whole-world revert.

```json
{
  "save_version": 1,
  "name": "string (save name)",
  "created": "ISO timestamp",
  "session_number": 5,
  "snapshot": {
    "campaign-overview.json": {},
    "npcs.json": {},
    "locations.json": {},
    "facts.json": [],
    "plots.json": {},
    "items.json": {},
    "consequences.json": {},
    "ruleset.json": {},
    "world-bible.json": {},
    "threat-clocks.json": {},
    "world-tick-log.json": {},
    "combat_state.json": {},
    "rule-state.json": {},
    "session-log.md": "text...",
    "fallen/hero.json": {},
    "characters": { "character": {} }
  }
}
```

---

## Validation Notes

- All timestamps use ISO 8601 format with timezone
- Entity names serve as dictionary keys (case-sensitive)
- Empty arrays `[]` are preferred over `null` for list fields
- Boolean fields default to `false` if omitted
- The `created` field is auto-set by managers when entities are created

## ruleset.json

The world's own rules, on top of the repo's. Made by `gm-rule.sh define`; a world
without rules of its own has no file.

```json
{
  "rules": [
    {"name": "Bleed", "block": "counter", "held_by": "player", "known": true,
     "range": [0, 6], "start": 0,
     "summary": "what it is about", "when": "when the GM changes it", "notes": "the rest",
     "results": [{"from": 2, "text": "what happens"}, {"from": 0, "to": 1, "text": "only in 0–1"}]}
  ],
  "plain_rules": ["Credits are zeds (Lull scrip). A meal costs 1."]
}
```

- `rules` and `plain_rules` are written by `gm-rule.sh define` and `plain`
  (`lib/world_rules.py`); every rule is checked when it is defined.
- The attributes are not set here: every campaign uses the nine in `lib/skill_contest.py`.
  Growth is the same for every campaign (`lib/growth.py`).

## rule-state.json

Where each of the world's own rules stands, per holder (the facts' ids, plus
`world`; in a campaign without `factions.json`, `faction:<id>` names a faction of the bible's
older factions graph). A value is stored once it is set or
changes; until then it is the rule's `start`.

```json
{
  "player": {"Bleed": {"value": 4, "on": ["from 2", "from 4"], "since": "2089-08-15T22:10"}},
  "faction:lull": {"Patience": {"value": 1, "on": ["from 0 to 1"], "known": true}},
  "location:The Middens": {"Heat": {"value": 4, "on": ["from 3"]}}
}
```

`on` lists the results on now, `since` the game time of the last change, `known` is
there only when one holder's value differs from the rule's.

## world-bible.json (Book Bible)

The structured fidelity spine of a world, loaded at session start. Auto-drafted at
import; captures what makes a book feel like itself.

```json
{
  "name": "string",
  "voice": { "style": "string", "vocab": ["..."], "sample_passages": ["..."] },
  "tone": "string",
  "themes": ["..."],
  "geography": { "nodes": [{"id","name"}], "edges": [{"from","to","adjacency"}] },
  "timeline": ["..."],
  "index": {
    "npcs":      [{"name": "string", "note": "one sentence"}],
    "locations": [{"name": "string", "note": "one sentence"}],
    "items":     [{"name": "string", "note": "one sentence"}],
    "monsters":  [{"name": "string", "note": "one sentence"}]
  }
}
```

`index` is the named-entity roster — the things the book already named, one sentence each
— scaffolded empty by `draft-bible` and surfaced as the scene-context WORLD INDEX block so
the GM reuses an established name before inventing one. It is optional (absent on legacy
bibles); when present, `validate_bible` requires the four buckets to be lists of
`{"name","note"}` objects. `segment_into_chapters` still splits the source, but now only
feeds the RAG coarse index (`lib/rag/coarse_index.py`) — it no longer writes into the
bible.

Required: name, voice, tone, themes, geography (graph). The factions and their ties are in
`factions.json`; an older bible lists them as a `factions` graph, and in a campaign without
`factions.json` those are its factions. The world's
own rules are in `ruleset.json` (`gm-rule.sh define`).

## factions.json

The campaign's factions (`lib/factions.py`, `gm-faction.sh`), keyed by a short id that
never changes: `faction:<id>` is how facts, triggers and world rules name it. The record
only describes the faction; its goal is a plot it owns, its secrets are facts it holds,
its own numbers are world rules held by factions.

```json
{
  "lull": {"name": "Lull Corporation", "aliases": ["Lull"], "kind": "megacorp",
           "description": "one or two sentences",
           "impulses": ["what drives it"], "values": ["what it stands for or never does"],
           "leader": "npc:<key>", "successor": "npc:<key>",
           "assets": [{"name": "The Mesh", "note": "one sentence"}], "tags": ["corp"],
           "ties": {"psm": "how Lull sees PSM, one line"}}
}
```

Only `name` and `description` are required. A leader or successor is also a member. `ties`
(`gm-faction.sh tie`): the history with another faction as this one sees it; the number
is the Relation (a world rule held by the pair).

**Membership** is on the NPC's sheet, `identity.factions`: `[{"id": "lull"}, {"id": "coven",
"secret": true}]` (`gm-faction.sh join` / `leave`, `gm-npc.sh create --faction`). An NPC knows
a fact they hold or one held by a faction they belong to (`factions.knows`); joining fires
their `on_learn` consequences for the faction's facts, and what a faction learns its living
members learn. `secret`: only the faction's members know of it (marked on the card; anyone
else finding out is a fact). The first `gm-faction.sh create` in a campaign
whose bible lists factions as `nodes` copies those in first, so values they hold carry over.

A `confirmed: false` flag on a freshly auto-drafted bible holds the world for human review;
**an absent flag counts as confirmed**, so hand-authored and legacy bibles are playable
immediately. See [the World Bible](modules/world-bible.md).

---

## Related

- [The entity graph](modules/entity-graph.md) — why these files cross-reference by name
- Extraction schema is not the runtime schema
- [Importing a book](flows/import-a-book.md) — how these files get populated
