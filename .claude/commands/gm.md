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
| save | Jump to SAVE SESSION section |
| character | Jump to CHARACTER DISPLAY section |
| overview | Jump to CAMPAIGN OVERVIEW section |
| status | Run `bash tools/gm-overview.sh` and display results |
| end | Jump to ENDING SESSION: record what is, invent nothing |
| cliffhanger | Jump to ENDING SESSION, ending on a cliffhanger |
| world | Jump to OFF-SCREEN DEVELOPMENTS (does not end the session) |
| world cliffhanger, cliffhanger world | OFF-SCREEN DEVELOPMENTS first, then ENDING SESSION on a cliffhanger |
| choices [on\|off\|toggle] | Run `bash tools/gm-session.sh choices <arg>`, confirm the new play style, and continue the current scene in it |

---

## ACTION MENU (PLAY STYLE)

The GM can end each beat with exactly three numbered action options followed by a
final "Or something else..." line (so the player always knows they can act freely),
or with an open prompt and no menu. This is a per-campaign, player-togglable preference
(`preferences.action_menu`, default ON) surfaced in `gm-session.sh context`.
Beat shape and pacing live in CLAUDE.md and the session brief — do not duplicate
them here.

- Toggle explicitly: `bash tools/gm-session.sh choices on|off|toggle` (no arg shows state).
- Toggle by asking mid-play ("stop giving me choices", "give me options again"):
  detect the intent, run the command to persist it, then continue the scene in
  the new style without re-narrating.

When OFF, still resolve actions and prompt the player — just close with an open
question instead of a numbered list.

---

## STEP 0: CAMPAIGN SELECTION

**ALWAYS display the campaign selection menu first.**

```bash
bash tools/gm-campaign.sh list
```

### Display Campaign Menu

Show a numbered list of saved campaigns (name, character, race/class/level, session count, last location), mark the active one, and always end with NEW ADVENTURE. Wait for a number. No fenced boxes; phone-friendly.

### Menu Logic

1. **List all campaigns** with number indices starting at 1
2. **Always include** `[N] NEW ADVENTURE` as the final option
3. **Show for each campaign:**
   - Campaign name
   - Character name, race, class, level
   - Session count
   - Last known location
4. **Mark active campaign** with `*` or `►` indicator
5. **Wait for user selection**

### After Selection

- **If user picks a campaign number** → `bash tools/gm-campaign.sh switch <name>` then go to CONTINUE CAMPAIGN
- **If user picks N (new)** → Go to NEW CAMPAIGN

---

## NEW CAMPAIGN

Offer three numbered starts: CREATE WORLD (full setting from scratch), IMPORT DOCUMENT (PDF, book, or module), ONE-SHOT (quick adventure). Wait for a number. No fenced boxes; phone-friendly.

- If CREATE WORLD → Run `/new-game`
- If IMPORT DOCUMENT → Run `/import`
- If ONE-SHOT → Go to ONE-SHOT ADVENTURE

---

## ONE-SHOT ADVENTURE

One-shots start fast and stay tight; pick a hook that fits the player's appetite.

### Character Creation

Run the `/create-character` interview. For a one-shot, use its fast way: ask for a one-line
concept, propose a complete character, let the player change what they like, save.

### Temporary World State

Create minimal world state:
```bash
bash tools/gm-campaign.sh create "one-shot" --campaign-name "One-Shot Adventure"
bash tools/gm-campaign.sh switch "one-shot"
bash tools/gm-location.sh add "<opening place>" "<one line about it>"
bash tools/gm-npc.sh create "<first NPC>" "<who they are>" "<attitude>" --location "<opening place>"
bash tools/gm-session.sh move "<opening place>"
bash tools/gm-scene.sh enter "<first NPC>"
```

### Begin Adventure

Jump into the opening scene. Option to convert to a full campaign at the end.

---

## ENTERING A WORLD (identity-first — the default)

A player arrives with an "I love this book" spike. They came to *talk to someone*.
Spending that on ability scores — or on extracting every city in the book — wastes it.
Entry costs **one question**: *"Who are you in this world — or who did you come to meet?"*

Ask it in the world's tone. Two answers: **someone from this world** (an NPC in the
campaign; offer names that actually exist, scene context and `gm-npc.sh` know who they are)
or **someone of their own** (a one-line concept). Then run the `/create-character`
interview, the fast way by default: propose a complete character, let the player change
what they like, save with `gm-player.sh create` (`--canon "<NPC>"` for someone from this
world). Don't interrogate a player who wants to start playing.

`create` refuses to overwrite a campaign that already has a PC (it names who is sitting
there). That refusal is a signal you asked the question at the wrong moment — check before
you offer. If the player really is handing the story to someone new, add `--replace`, which
archives the outgoing sheet to `fallen/` first.

**After identity, before you open the scene, ask where/when they want to start.** Offer a
fitting default (an iconic opening for this world/character) but make it plain they can name
their own: a specific location, a particular scene, or a point in the timeline. Build the
opening around **that** start and write it in one call: `bash tools/gm-session.sh opening '<json>'`
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
This single command gives you: character stats, party members (with recent events), pending consequences, campaign rules, location, and time. Read and internalize ALL of it.

For the latest facts in full (who knows them, what is true), run `bash tools/gm-note.sh recent 15`; for anything else, `gm-note.sh find` (by who knows it, who it's about) and `gm-note.sh show <id>`. Never read `facts.json` or the other campaign files yourself.

**If there is no character yet** (no `character.json` / the context shows no active PC), don't
narrate a scene into a void and don't launch the 9-step builder — go to ENTERING A WORLD
below, ask the one question, then come back and finish the checklist.

**Campaign Rules:** If the context output shows campaign-specific rules, enforce them throughout the session just like core rules. Each campaign is different.

#### Step 2: Verify Location (CRITICAL)
```bash
tail -30 world-state/campaigns/[campaign-name]/session-log.md
```
- [ ] Find the LAST session's ending location in the log
- [ ] Compare to location from Step 1
- [ ] **If mismatch**: Session log is truth. Run:
  ```bash
  bash tools/gm-session.sh move "[correct location]"
  ```

#### Step 3: Who is in the scene
```bash
bash tools/gm-scene.sh
```
The scene list (who is actually here) decides who learns what is said, and which NPCs the
brief shows. It starts empty after a move. If the cliffhanger has someone with the character,
enter them: `bash tools/gm-scene.sh enter "<name>"...`.

#### Step 4: Party context

Pull full NPC detail when the summary isn't enough:
```bash
bash tools/gm-npc.sh status "[name]"
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

## GAMEPLAY LOOP

Now you're playing. For every player action, follow the workflows in CLAUDE.md:

1. **Understand Intent** - What workflow applies?
2. **Execute** - Use tools invisibly
3. **Persist** - Save all state changes
4. **Narrate Result** - Describe what happens
5. **Enforce Campaign Rules** - Apply any campaign-specific rules from campaign-overview.json's `campaign_rules` section
6. **Growth** - An achievement just happened? Award it (`gm-growth`). Growth due and a quiet moment? Run it (`gm-growth`)
7. **Ask** - "What do you do?"

Repeat.

---

## ENDING SESSION

When the player says they're done, or types `/gm end`: **record what is, invent nothing.**

```bash
bash tools/gm-session.sh end "<summary of what happened>" --cliffhanger "<the situation as it stands>" --open-thread "<...>"
bash tools/gm-recall.sh arc '{"summary": "...", "who_matters": [...], "open_debts": [...]}'
```

- **The cliffhanger is where we paused,** exactly as it stands: where the character is, what's unresolved, who's waiting, what's at stake. If the player stopped mid-action, record it mid-action. No new events, twists, arrivals or reveals, and no off-screen developments.
- **`/gm cliffhanger`:** the same, but you may close on a real new development: a twist, an arrival, a reveal. Persist it properly as well (a fact, a consequence or a plot), not only in the cliffhanger, so the next session treats it as established.

Confirm the session is saved: who rests where, and that progress is recorded. No fenced boxes; phone-friendly.
This confirmation is for the player, so the fourth wall holds (`CLAUDE.md` → Dice): tell only
what the character knows. Never mention threat clocks, due times, pending consequences or
anything still to come ("the priests come for Ishbel at 16:30" is the GM's knowledge). A
portent that has already happened in play may be recalled ("something on Level 18 scraped,
then went still"). No numbers: no wound counts, rolls or difficulties ("the knee is wrenched",
not "1 wound").

---

## OFF-SCREEN DEVELOPMENTS

**Invoked via:** `/gm world`. Only when the player asks; never on your own, and never as part of a plain `/gm end`.

The world moves while the character is away or resting: the end of a session, a long rest, a week in hiding. Propose a few SMALL developments grounded in the plots, clocks, consequences and NPC goals. Each development is something that **has happened** off-screen, so it is always a fact. If it also sets something in motion, add a consequence with a real trigger (who or where it waits for), and/or a clock for a time limit:

```bash
bash tools/gm-session.sh world-tick '[
  {"fact": "Meridian has posted foreclosure notices across Level 40."},
  {"fact": "Dekker has hired a tracker who hunts the grey sleeve.",
   "consequence": {"text": "The tracker finds Fearghas",
                   "triggers": [{"type": "on_location", "match": "Old Iron'"'"'s Yard"}]},
   "clock": {"name": "The tracker closes in", "segments": 3, "due_in": "3d",
             "consequence": "The tracker finds Fearghas"}}
]'
```

- `fact` (required): what happened, one line. Optional `"category"` (default `plot_local`, shown under KEY FACTS) and `"about"`: a list of ids (`npc:<name>`, `location:<name>`, `player`) the text doesn't name; names in the text are added by themselves. Optional `"holders"`: who knows it (`npc:<name>`, `street`, `public`, `player`); default nobody, since it happened off-screen. Optional `"at"`: where it happened (a known place); default none. Optional `"truth": "wrong"` or `"partial"` with `"version_of": "<fact id>"`: a cover story, a planted lie.
- `consequence` (optional): `text` plus `triggers`, the same types as `gm-consequence.sh add` (`on_location`, `on_npc`, `on_time`, `on_death`, `on_clock`, `on_learn`, `on_event`). A consequence without triggers is refused.
- `clock` (optional): `name`, `segments`, and `due_in` (`3d`) or `due` (`"YYYY-MM-DD HH:MM"`) for a time clock, or `"on": "event"` for one you advance by hand; `consequence` fires when it fills.

It applies all of them (warns if more than 3). If any part is invalid, nothing from the tick is kept: fix it and send the whole list again. Afterwards it lists the consequences waiting on an event: if a development fulfils one, fire it (`gm-consequence.sh fire <id> --by <fact id>`). `gm-session.sh world-tick-rollback` undoes the last tick: its facts, consequences and clocks. Tell the player only what the character could know, or nothing, and let the rest surface in play. `/gm world` does not end the session; with `cliffhanger` as well, end the session on a cliffhanger afterwards.

---

## CHARACTER DEATH (mid-session hand-off)

PC death is **NOT** the end-session path above. Death does not close the game — it routes to the **Death Protocol** in CLAUDE.md and play continues with a new active PC.

When the PC dies (see Stakes & Death in CLAUDE.md and the wound rules in `gm-combat`):

1. **Persist first** — `bash tools/gm-player.sh kill "<name>" --cause "<how>"` (sets status dead, stamps died_at, records the death as a fact, fires `on_death player` consequences), record any further consequence (`gm-consequence.sh add`).
2. **Narrate the death** with weight. No menu yet.
3. **Offer the hand-off** (the show goes on — not GAME OVER). The three routes — take over a party member already in the scene, roll a new character, or step in as a canon figure from the source. Frame them however CLAUDE.md's Death Protocol calls for. (If solo with no party and no fitting canon figure, offer the last two only.)
4. **SWAP in the new PC:**
   - New character → run the `/create-character` interview and save with `gm-player.sh create '<json>' --replace`.
   - A party member or a canon figure → the same interview, a canon character with that NPC's data as the first suggestion, saved with `gm-player.sh create '<json>' --canon "<NPC>" --replace`.
   - Either way the fallen PC's sheet goes to `fallen/`, and they become an NPC with what they knew; the new character knows only what they witnessed or were told (`gm-note.sh witness` / `tell`), and a canon character keeps what the NPC knew.
5. **Bridge the fiction** (how/why control passes), update location/scene, then resume play. The dead hero stays in the world's memory — referenced, mourned, looted, avenged. Threads and clocks persist.

---

## SAVE SESSION

**Invoked via:** `/gm save`

Execute comprehensive save workflow:

### 1. End Session with Summary
```bash
bash tools/gm-session.sh end "[brief summary of key events]"
```

### 2. Verify State Updates
Ensure all changes from the session are persisted:
- Wounds, armor, cyberware → `gm-body.sh`
- Inventory changes → `gm-player.sh inventory`
- Credits changes → `gm-player.sh credits`
- NPC updates → `gm-npc.sh update`
- Location changes → `gm-session.sh move`
- Consequences → `gm-consequence.sh add`
- Facts → `gm-note.sh`

### 3. Run Verification
```bash
bash tools/gm-session.sh status
bash tools/gm-consequence.sh check
```

### 4. Display Confirmation

Confirm the save: who rests where, and that NPCs, locations, consequences, and the session log were updated. No fenced boxes; phone-friendly.

---

## CHARACTER DISPLAY

**Invoked via:** `/gm character`

### 1. Get Active Character
```bash
bash tools/gm-player.sh get "<name>"
bash tools/gm-body.sh show
```

### 2. Display Character Sheet

Present the finished sheet clearly, phone-friendly: name, level, race, class, background, attributes (as die sizes), skills, luck, traits, perks, the campaign's own counters, the body picture with its notes, armor and cyberware, features, credits, and inventory. No fenced boxes.

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

Show campaign name, current location/time/character/session count, and world counts (NPCs, locations, facts, active consequences). No fenced boxes; phone-friendly.

### 3. Show Active Consequences
```bash
bash tools/gm-consequence.sh check
```

---

That's it. One command. Infinite adventure.
