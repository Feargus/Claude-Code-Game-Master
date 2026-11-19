# /gm - Your AI Game Master

One command. Instant immersion. Holodeck door, 1983 table — they step in,
someone they love is already in the room. The book stays on your chair. Do not
open with a gazetteer. See `docs/conventions/the-dream.md`.

---

## SUBCOMMAND ROUTING

When user invokes `/gm <subcommand>`, route to the appropriate section:

| Subcommand | Action |
|------------|--------|
| (none) | Continue to STEP 0: CAMPAIGN SELECTION below |
| character | Jump to CHARACTER DISPLAY section |
| overview | Jump to CAMPAIGN OVERVIEW section |
| status | Run `bash tools/gm-overview.sh` and display results |
| end | Jump to STOPPING FOR NOW: record what is, invent nothing |
| cliffhanger | Jump to STOPPING FOR NOW, ending on a cliffhanger |
| world | Jump to OFF-SCREEN DEVELOPMENTS (does not stop play) |
| world cliffhanger, cliffhanger world | OFF-SCREEN DEVELOPMENTS first, then STOPPING FOR NOW on a cliffhanger |
| choices [on\|off\|toggle] | Run `bash tools/gm-session.sh choices <arg>`, confirm the new play style, and continue the current scene in it |

---

## STEP 0: CAMPAIGN SELECTION

**ALWAYS display the campaign selection menu first.**

```bash
bash tools/gm-campaign.sh list
```

### Display Campaign Menu

Show a numbered list of saved campaigns (name, character, race/role/level, last location: all in `gm-campaign.sh list`), mark the active one, and always end with NEW ADVENTURE. Wait for a number. No fenced boxes; phone-friendly.

### Menu Logic

1. **List all campaigns** with number indices starting at 1
2. **Always include** `[N] NEW ADVENTURE` as the final option
3. **Show for each campaign:**
   - Campaign name
   - Character name, race, role, level
   - Last known location
4. **Mark active campaign** with `*` or `►` indicator
5. **Wait for user selection**

### After Selection

- **If user picks a campaign number** → `bash tools/gm-campaign.sh switch <name>` then go to CONTINUE CAMPAIGN
- **If user picks N (new)** → Go to NEW CAMPAIGN

---

## NEW CAMPAIGN

Two questions make a new campaign; ask them in plain text, numbered, phone-friendly.

**1. How do we make the world?**
1. **Together:** a conversation about premise, tone, voice and the world's own systems, then you build it and the player approves it. → `/new-game`
2. **From one sentence:** the player gives one sentence ("a drowned arcology where the rich live on the roof"), you build the setting and lore from it without further questions. The repo's rules only: no rules of its own. → `/new-game`, QUICK WORLD
3. **From a book:** a PDF, book or module the player provides. → `/import`

**2. How do we make the character?** Fast or slow, and someone of their own or someone from this world: the `/create-character` interview asks this, at the point each path hands over to it.

Every path ends the same way: the interview saves the character (`gm-player.sh create`), then `gm-session.sh opening` writes the first scene with its plot, hook, clock and start time.

---

## ENTERING A WORLD (identity-first — the default)

A player arrives with an "I love this book" spike. They came to *talk to someone*.
Spending that on ability scores — or on extracting every city in the book — wastes it.
Entry costs **one question**: *"Who are you in this world — or who did you come to meet?"*

Ask it in the world's tone. Two answers: **someone from this world** (an NPC in the
campaign; offer names that actually exist, scene context and `gm-npc.sh` know who they are)
or **someone of their own** (a one-line concept). Then run the `/create-character`
interview, fast (the default: one complete proposal) or slow (entry by entry), and save
with `gm-player.sh create` (`--canon "<NPC>"` for someone from this world). Don't
interrogate a player who wants to start playing.

`create` refuses to overwrite a campaign that already has a PC (it names who is sitting
there). That refusal is a signal you asked the question at the wrong moment — check before
you offer. If the player really is handing the story to someone new, add `--replace`, which
archives the outgoing sheet to `fallen/` first.

**After identity, before you open the scene, ask where/when they want to start.** Offer a
fitting default (an iconic opening for this world/character) but make it plain they can name
their own: a specific location, a particular scene, or a point in the timeline. Build the
opening around **that** start and write it in one call: `bash tools/gm-session.sh opening <<'EOF'`, the JSON, a line `EOF`
(the place, its exits, the people there, the plot and its hook, the premise and secrets, the
antagonist's clock, the start time; the fields and an example: `lib/opening.py` and
`/new-game` Phase D). Then narrate the first scene from what it prints.

---

## CONTINUE CAMPAIGN

### Startup

Complete Steps 1-3 before presenting the scene. Do not skip them.

#### Step 1: Load Full Context (PRIMARY)
```bash
bash tools/gm-session.sh start
bash tools/gm-session.sh context
```
This single command gives you: the plots (with their clocks, waiting consequences and secrets), the character, the campaign's rules, the newest facts, the scene, location and time. Read and internalize ALL of it.

The brief's LATEST lists the newest facts not shown above it. For more, filter, usually by two things: `bash tools/gm-note.sh find --about "npc:<who>" --at "<where>"`, or `--plot "<plot>"`, `--held-by "<who>"`; `gm-note.sh show <id>` for one in full. Never read `facts.json` or the other campaign files yourself.

**If there is no character yet** (no `character.json` / the context shows no active PC), don't
narrate a scene into a void and don't launch the 9-step builder — go to ENTERING A WORLD
below, ask the one question, then come back and finish the checklist.

**Campaign Rules:** If the context output shows campaign-specific rules, enforce them throughout the session just like core rules. Each campaign is different.

#### Step 2: Where the story stands
The brief's location, time, plots and facts are the truth: every move, time step and fact
is recorded as it happens. A plot's "stands" is one sentence the GM wrote when it last
moved, so it can be older than the plot's latest facts: the brief's LATEST shows them. If something still doesn't add up, ask the player out of character before
narrating (`CLAUDE.md` → Scene context).

#### Step 3: Who is in the scene
The brief's THE SCENE shows the place and everyone in it as cards. The scene list (who is
actually here) decides who learns what is said, and whose cards are shown. It starts empty
after a move. If the cliffhanger has someone with the character, enter them:
`bash tools/gm-scene.sh enter "<name>"...` (it prints their card).

#### Step 4: Party context

Pull full NPC detail when the summary isn't enough:
```bash
bash tools/gm-npc.sh show "[name]"
```

---

### Using Source Material (GM-Internal)

When `gm-session.sh start` or `move` runs, it queries source material for the current location. The context appears as `[GM Context: ...]` in the tool output - this is for **your eyes only**, not the player's.

**How to use GM Context:**
- Read the context hints internally to understand the scene
- Ground descriptions in source material tone and details
- Reference specific sensory details from the original
- Match NPC dialogue to their canonical voice
- Capture the author's writing style and atmosphere

**CRITICAL: Do NOT paste raw passages into narrative.** Synthesize them into natural scene descriptions.

---

### Present Scene

Show where they are, who is present, and what is happening, plus the header vitals (level, wounds, XP, credits, status). No fenced boxes; phone-friendly.

During a fight, convey who is acting, each enemy's state (wounded, disabled parts, out), and the result. When loot lands, convey what was found and its worth (persist first).

---

## PLAY

From here on, every turn follows `CLAUDE.md`: the core loop, the dice, persistence and
the play style the brief reports.

---

## STOPPING FOR NOW

When the player says they're done, or types `/gm end`: **record what is, invent nothing.**
Everything that happened is on disk already (persist before narrating). What is left:

- **For each plot that moved,** rewrite where it stands, one sentence for the whole state
  or its major turns, not every detail: `bash tools/gm-plot.sh stands "<plot>" "<…>"`.
  A plot that ended: `gm-plot.sh complete|fail "<plot>" "<what came of it>" [--next "<plot>"]`.
- **Stop where the story is.** If the player stopped mid-action, that is where the next
  time begins: no new events, twists, arrivals or reveals, and no off-screen developments.
- **`/gm cliffhanger`:** the same, but you may close on a real new development: a twist,
  an arrival, a reveal. Persist it properly (a fact, a consequence, a plot's `stands`), so
  the next time treats it as established.

Tell the player where the story rests: who is where, and that it is all recorded. No fenced boxes; phone-friendly.
This confirmation is for the player, so the fourth wall holds (`CLAUDE.md` → Dice): tell only
what the character knows. Never mention threat clocks, due times, pending consequences or
anything still to come ("the priests come for Ishbel at 16:30" is the GM's knowledge). A
portent that has already happened in play may be recalled ("something on Level 18 scraped,
then went still"). No numbers: no wound counts, rolls or difficulties ("the knee is wrenched",
not "1 wound").

---

## OFF-SCREEN DEVELOPMENTS

**Invoked via:** `/gm world`. Only when the player asks; never on your own, and never as part of a plain `/gm end`.

The world moves while the character is away or resting: the end of a session, a long rest, a week in hiding. **First the factions take a turn** (below, if the campaign has factions), **then** the people.

### The factions' turn

Factions also act between `/gm world`s: the faction bag draws them as game time passes, and the turns it draws are listed as FACTION TURNS OWED (after a time step or a journey, and in the brief). Play each when it is listed, oldest first: `gm-faction.sh turn --only <faction>` with that faction's one action, or a full turn for a joker; it settles the owed turn. Record its facts at the time it was drawn: `--when "<time>"` (in a beat `"when"`), as the output says. Same rules as below.

You play the factions; the script referees. Read each faction (`gm-faction.sh show <id>`: its plot, power, presence, relations, members) and give **every faction one action** (a faction that lies low builds up; a turn with one missing is refused), mostly from its current plot: the plot is its plan, its values and impulses made concrete. Play to its strengths (strong in Political: it talks, it doesn't shoot). Prefer actions that leave a thread the character can pull (a kidnapping, not a killing; a theft, a lie that can be exposed). Give them all at once: each is judged from the state before any of them, and the script applies everything together.

```bash
bash tools/gm-faction.sh turn <<'EOF'
[{"faction": "kin", "action": "build", "power": "Political", "note": "door-to-door in Lowtown"},
 {"faction": "hardtop", "action": "push", "power": "Economic", "rival": "kin", "at": "Culvert Street"},
 {"faction": "almanac", "action": "prepare"},
 {"faction": "afters", "action": "strike", "power": "Military", "rival": "hardtop", "at": "The Spine"}]
EOF
```

- **Simple, numbers only, never a cost:** `build` (+1 to +3 power), `reinforce` (+1 or +2 presence `at` a place), `push` (a `rival`'s presence `at` a place −0 to −2, contested), `prepare` (its plot's plan clock +1; the portents on it fire by themselves).
- **Complex, they cost 2 of the power used (3 if they fail) and make facts:** `strike` (rival's presence −1 to −3), `seize` (an `asset` of the rival, or a place: ±1 or ±2), `take` (`who`: kidnap, arrest, blackmail; the `rival` is whoever protects them, or none), `spy` (learn a fact the rival holds), `expose` (a fact about the rival up the ladder), `deal` (a pact, a truce, a bribe), `enact` (the plot's goal, when its plan clock is full).
- **Contests:** d6 + the power used against d6 + the rival's same power. A defender has no action; its power is its defence.
- **After the turn:** for each complex action the output says what to record. Record at least two facts with `gm-note.sh beat`: the truth, held by the acting faction, and versions for the others (`"truth": "partial"` or `"wrong"`, `"version_of": "#1"`, held by the victims, the street or the public: "a gas main blew at the depot"). An `enact` ends its plot (`gm-plot.sh complete|fail`) and needs the next one (below). A deal's terms, and the lasting effects of a plot's success or failure, are consequences that move resting points (`--rule-effect '{"rate_of": "Relation", "of": "kin+hardtop", "shift": 1}'`). Simple actions need nothing: a change of presence is background (more patrols, a shop shut), narrated only if the character is there.
- A turn can't be undone (every power change is in `rules.log`). Faction actions are about the world, not the character: their facts are held by factions, the street or the public, and time doesn't stop for them.

**A faction's plot** (its first, and each that replaces it) is written from its values and impulses and where it stands now: power, assets, leader, presence, relations. With it, in one go:
1. `gm-plot.sh add "<short name>" --owner faction:<id> --goal "<what they are after>" --description "…"`;
2. its plan clock, an event clock: `gm-clock.sh add "<short name>" <2–6> --on event --text "<the plan>" --plot "<plot>"`;
3. the true plan as a fact the faction holds (`gm-note.sh "<the plan>" --holders faction:<id> --nowhere --plot "<plot>"`);
4. its portents: a lie or a half-truth each, recorded as a secret version of the plan (`--secret --truth wrong|partial --version-of <id>`), and an `--offscreen` consequence that tells it to the street or the public when the clock reaches its segment (`--trigger-type on_clock --match "<clock>:<segment>" --tells <id> --to street`). One portent on a clock of 2–3 segments, two on 4–6, spread evenly.

### The people

Then propose a few SMALL developments grounded in the plots, clocks, consequences and NPC goals. Each development is something that **has happened** off-screen, so it is always a fact. If it also sets something in motion, add a consequence with a real trigger (who or where it waits for), and/or a clock for a time limit:

```bash
bash tools/gm-session.sh world-tick <<'EOF'
[
  {"fact": "Meridian has posted foreclosure notices across Level 40."},
  {"fact": "Dekker has hired a tracker who hunts the grey sleeve.",
   "consequence": {"text": "The tracker finds Fearghas",
                   "triggers": [{"type": "on_location", "match": "Old Iron's Yard"}]},
   "plot": "Vey Inheritance",
   "clock": {"name": "Tracker", "text": "The tracker closes in", "segments": 3, "due_in": "3d",
             "consequence": "The tracker finds Fearghas"}}
]
EOF
```

- `fact` (required): what happened, one line. Optional `"about"`: a list of ids (`npc:<name>`, `location:<name>`, `player`) the text doesn't name; names in the text are added by themselves. Optional `"holders"`: who knows it (`npc:<name>`, `street`, `public`, `player`); default nobody, since it happened off-screen. Optional `"at"`: where it happened (a known place); default none. Optional `"truth": "wrong"` or `"partial"` with `"version_of": "<fact id>"`: a cover story, a planted lie.
- `plot` (optional): the plot the development belongs to; its fact, consequence and clock all join it.
- `consequence` (optional): `text` plus `triggers`, the same types as `gm-consequence.sh add` (`on_location`, `on_npc`, `on_time`, `on_death`, `on_clock`, `on_learn`, `on_event`). A consequence without triggers is refused.
- `clock` (optional): `name` (a short key of one to three words, which triggers and commands use: `on_clock` `"Tracker:2"`), `text` (what it is about), `segments`, and `due_in` (`3d`) or `due` (`"YYYY-MM-DD HH:MM"`) for a time clock, or `"on": "event"` for one you advance by hand; `consequence` fires when it fills.

It applies all of them (warns if more than 3). If any part is invalid, nothing from the tick is kept: fix it and send the whole list again. Afterwards it lists the consequences waiting on an event: if a development fulfils one, fire it (`gm-consequence.sh fire <id> --by <fact id>`). `gm-session.sh world-tick-rollback` undoes the last tick: its facts, consequences and clocks. Tell the player only what the character could know, or nothing, and let the rest surface in play. `/gm world` does not end the session; with `cliffhanger` as well, end the session on a cliffhanger afterwards.

---

## CHARACTER DISPLAY

**Invoked via:** `/gm character`

### 1. Get Active Character
```bash
bash tools/gm-player.sh get
bash tools/gm-body.sh show
```

### 2. Display Character Sheet

Present the finished sheet clearly, phone-friendly: name, level, race, role, background, attributes (as die sizes), skills, luck, traits, perks, the world's own rules the character holds, the body picture with its notes, armor and cyberware, features, credits, and inventory. No fenced boxes.

If no active character: don't print a sheet — ask the one question (see ENTERING A WORLD)
and run the `/create-character` interview.

---

## CAMPAIGN OVERVIEW

**Invoked via:** `/gm overview`

### 1. Load Campaign Info
```bash
bash tools/gm-campaign.sh info
```

### 2. Display Campaign State

Show campaign name, current location/time/character, and world counts (NPCs, locations, facts, active consequences). No fenced boxes; phone-friendly.

### 3. Show Active Consequences
```bash
bash tools/gm-consequence.sh check
```

---

That's it. One command. Infinite adventure.
