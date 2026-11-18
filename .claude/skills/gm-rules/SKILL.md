---
name: gm-rules
description: Making a world's own rules (Bleed, a sea level, a gang's patience) from the building blocks, while the player describes the world and their character. Load in /new-game (Together) and /import, before the bible is approved. Not needed in play: the brief and gm-rule.sh carry everything then.
---

# The world's own rules

Every campaign plays by the repo's rules: skill contests (`gm-skills`), wounds
(`gm-combat`), growth (`gm-growth`), clocks, consequences and facts. A world adds a
few rules of its own on top: what makes playing in it feel unlike anywhere else.
Bleed in a city that leases its sleepers' minds; the sea level in a drowning city;
how much more a gang will put up with.

You make them **with the world**, while the player describes it and their
character. In play the brief shows each rule in full (YOUR WORLD'S RULES), and
`gm-rule.sh` changes them and prints what follows; this skill isn't needed again.

## 1. Listening for rules

While the player talks about the world, listen for something play will touch
often and that the repo's rules don't already cover:

| You hear | The block (§3) | Examples |
|---|---|---|
| a pressure that grows, a thing that wears down | **counter** | a debt, a city's fear, heat from the law, the water rising |
| ... and it moves by itself as time passes | counter with a **rate** | the sea rises a season at a time; patience comes back |
| ... and it can tip over and stays tipped a while | counter with **hysteresis** | panic that lifts only when calm returns; a riot |
| ... and it leaves scars when it fills | counter with **overflow** | stress that breaks into a phobia; a scandal that costs a board seat |
| a run of luck that one failure ends | counter with a **streak** | momentum in a chase; a fighter's unbeaten run |
| a price, a first reaction, a trap: decided once, by chance | **roll** | what sorcery costs; how a gang meets a stranger; a cursed hoard |
| stages with a way in and, perhaps, no way back | **states** | addiction; a corporation's alert; a contact's trust |
| two things that only matter together | **plane** | chrome against what ties you to people; law against good |
| luck that runs out as things go wrong | **bag** | a job's luck; the years of the melt |
| never enough time or people for everything | **budget** | a week of downtime; a gang's soldiers |

Prefer the simplest block that does the job: most rules are counters. Two separate
counters are better than a plane unless the combination matters.

A rule must matter in many scenes. Scenery is not a rule: the city's architecture
belongs in the bible, prices in a plain rule line (§4).

**What a rule is not:** anything the shared rules do. Actions are skill contests,
harm is wounds, deadlines are clocks, how someone feels about the character is an
attitude, who knows what is facts. A rule adds to these and never replaces one.

## 2. Suggesting them

Suggest **one to three** rules, each in one plain sentence, with what it adds to
play:

> "The water level could be a counter for the whole world, 0 to 10, rising a step
> every season: at 3 the Lower Docks flood at every tide, at 6 the ring road goes
> under."

> "Each job could have a bag of luck, eight clean tokens and two trouble: every risky
> step draws one, and every failed roll puts another trouble in."

The player picks, changes or drops them; you can offer two ways of modelling the
same thing. One rule that links to another (a warm year speeds up the sea, a lease
raises Bleed) makes a world feel alive; more than a link or two makes it hard to
follow. Show the chosen ones with the bible for approval, with their numbers.
Numbers are first guesses: play decides whether they are right.

## 3. The building blocks

Six blocks: **the counter** (one number, with a rate, hysteresis, overflow or a
streak), **the roll**, **states**, **the plane**, **the bag** and **the budget**, and
results that act. What no block can say goes into the rule's `notes`: the GM reads
them in the brief.

### Every rule: the shared fields

Every rule has these, whatever its block (the block's own fields follow below):

```json
{
  "name": "Bleed",
  "block": "counter",
  "held_by": "player",
  "known": true,
  "summary": "How much of other people's leased work has leaked into your head.",
  "when": "After every lease of the character's mind, and when they dive into the Mesh.",
  "notes": "A dry night (sleep without leasing) lowers it by 1, an illegal scrub by 2."
}
```

- **`name`**: a short key, one to three words, at most 30 characters, no colon.
  Commands use it, so it never changes. What the rule is about goes into the summary.
- **`held_by`**: who has a value of it: `player`, `npc`, `faction`, `location`,
  `world`, or a list of them. Each holder has its own value: with `"faction"`, every
  faction of the bible has its own Patience. `world` is one value for everything
  (the sea level).
- **`known`**: `true` (the default) means the HUD shows it and the narration can make
  it plain in the fiction, never with the number. `false` means the GM sees it and the
  player only its signs; every output marks it `[HIDDEN: show only its signs]`.
- **`summary`** (what it is about) and **`when`** (when the GM changes it) are
  required: without a `when`, a rule is forgotten in play. **`notes`** is for the rest.

### The counter: one number in a range

```json
{
  "name": "Bleed", "block": "counter", "held_by": "player",
  "range": [0, 6], "start": 0,
  "summary": "How much of other people's leased work has leaked into your head.",
  "when": "+1 to +2 after a lease, by its depth; +2 for a run through the Mesh.",
  "results": [
    {"from": 2, "text": "Intrusions: strangers' memories, jingles and flashes of skills never learned surface unbidden. They can help or betray."},
    {"from": 4, "text": "Lost time: under stress or asleep, something else drives the body for minutes. Narrate only what the character finds when they come back."},
    {"from": 6, "text": "Overwritten: the self goes quiet. Unless someone pulls the character back out of the Mesh within a day, they are gone (gm-player.sh kill)."}
  ]
}
```

- **`range`**: the lowest and highest value; a change stops at the ends.
- **`start`**: where every holder begins (default: the lowest).
- **`results`**: what values mean, each a `text` saying what happens in the fiction.
  A result holds **from** its value upward, so they add up: at Bleed 4 the intrusions
  still happen. With **`to`**, a result holds only in its range: `{"from": 0, "to": 1,
  ...}` is on at 0 and 1.

A counter held by the world:

```json
{
  "name": "Sea level", "block": "counter", "held_by": "world",
  "range": [0, 10], "start": 2, "rate": {"by": 1, "every": "90d"},
  "summary": "How far the sea has risen into the city since the ice shelves went.",
  "when": "It rises by itself; +1 for each great storm.",
  "results": [
    {"from": 3, "text": "The Lower Docks flood at every high tide; boats replace the tram there."},
    {"from": 6, "text": "The ring road is under water; the districts below it are islands."},
    {"from": 9, "text": "Only the towers stand above the water."}
  ]
}
```

A hidden counter held by factions, with results that hold only in a range:

```json
{
  "name": "Patience", "block": "counter", "held_by": "faction", "known": false,
  "range": [0, 5], "start": 5, "rate": {"by": 1, "every": "7d", "toward": 5},
  "summary": "How much more a faction will put up with from the character before it acts.",
  "when": "-1 for each slight: a missed payment, a refused job, a member embarrassed. It comes back by 1 a week.",
  "results": [
    {"from": 0, "to": 1, "text": "Warnings: a visit, a broken window, a message through a friend."},
    {"from": 0, "to": 0, "text": "They act.",
     "effects": [{"clock": "Retaliation", "start": 3, "text": "They come for the character", "due_in": "3d"}]}
  ]
}
```

A counter held by places and NPCs:

```json
{
  "name": "Heat", "block": "counter", "held_by": ["location", "npc"],
  "range": [0, 10], "start": 0, "rate": {"share": 0.5, "every": "1d", "toward": 0},
  "summary": "How much attention a place or a person has from the law after trouble.",
  "when": "+2 for a fight, +4 for a death. It cools by itself.",
  "results": [
    {"from": 3, "text": "Patrols pass by more often; the locals are tight-lipped."},
    {"from": 7, "text": "A checkpoint; faces are scanned; the law asks questions by name."}
  ]
}
```

### A counter's options

**A rate: it moves by itself as game time passes.** Every `gm-time.sh advance` (and
`move --takes`) moves it by the whole periods passed, with its results and effects;
a change by hand doesn't reset the count.

```json
"rate": {"by": 1, "every": "90d"}                    +1 every 90 days (the sea rises)
"rate": {"by": 1, "every": "7d", "toward": 5}         back by 1 a week, up to 5 (patience)
"rate": {"share": 0.5, "every": "1d", "toward": 0}    half the way to 0 a day (heat cools: 8, 4, 2, 1, 0)
```

With `toward`, `by` is the size of the step, and the value moves toward it from
either side: `{"by": 1, "every": "7d", "toward": 0}` heals 1 a week down to 0. Without
`toward`, `by`'s sign says which way, for ever (up to the end of the range).

The character's and the world's values move from the start; a faction's, a person's
or a place's from its first value (`gm-rule.sh set` at creation if it should move from
the start). One holder can get its own rate: `gm-rule.sh rate "<rule>" [holder] --by N
[--every 90d]`, or the effect `rate_of`: `{"rate_of": "Sea level", "by": 1}` (a warm
year speeds the sea up).

A hidden flaw that grows by itself:

```json
{"name": "Cascade", "block": "counter", "held_by": "player", "known": false,
 "range": [0, 5], "start": 0, "rate": {"by": 1, "every": "10d"},
 "summary": "The cheap arm from Doc Ferro has a firmware fault that is slowly getting worse.",
 "when": "It rises by itself; +1 when the arm takes a hit. A clinic's scan reveals it: gm-rule.sh reveal Cascade.",
 "results": [{"from": 2, "text": "A tremor in the left hand at bad moments: -1 to fine work with it."},
             {"from": 5, "text": "The arm dies. Until it is replaced, it is dead weight."}]}
```

**Hysteresis: on at one value, off only at another.** A result with `off_at` comes on
at its `from` and stays on until the value falls back to `off_at`:

```json
{"name": "Panic", "block": "counter", "held_by": "player", "range": [0, 8], "start": 0,
 "summary": "Fear building in a bad place.",
 "when": "+1 for each horror seen, each light that goes out, each friend lost from sight.",
 "results": [{"from": 6, "off_at": 2, "text": "Panicking: the character wants out, now. -2 to anything that isn't fleeing or hiding.",
              "effects": [{"condition": "Panicked"}], "when_off": [{"condition": "Panicked", "add": false}]}]}
```

A district's riot, held by places: `{"from": 8, "off_at": 3, "text": "Riot: ..."}`.

**Overflow: a lasting mark.** When the value reaches `at`, it goes back to `back_to`
and leaves a mark that never goes away. The output offers the suggestions; the GM
picks one that fits the moment, or writes one, and records it:
`gm-rule.sh mark "Stress" "night terrors"`. With `limit`, `at_limit` says what happens
when the marks reach it.

```json
{"name": "Stress", "block": "counter", "held_by": "player", "range": [0, 8], "start": 0,
 "summary": "What the job does to the character's nerves.",
 "when": "+1 to +3 when the character pushes themselves, takes a terrible risk, or sees something they can't unsee. A night off with friends: -2.",
 "overflow": {"at": 8, "back_to": 0,
              "marks": ["a stammer under pressure", "night terrors", "can't sit with their back to a door"],
              "limit": 3, "at_limit": "The character is done with this life: they retire. Load gm-death for the hand-off."}}
```

A corporation's scandals, held by factions: `"overflow": {"at": 5, "back_to": 1,
"marks": ["a board member resigns", "a government contract is lost"], "limit": 3,
"at_limit": "The corporation breaks up or is bought; its plots end."}`.

**A streak: one failure ends it.** `"streak": true`; each success `gm-rule.sh change
Momentum +1`, a failure `gm-rule.sh break Momentum` (back to its start).

```json
{"name": "Momentum", "block": "counter", "held_by": "player", "range": [0, 5], "start": 0, "streak": true,
 "summary": "A run of luck in a fight or a chase.",
 "when": "+1 for each success in a row in a fight or chase; any failure breaks it. It ends with the scene.",
 "results": [{"from": 3, "text": "On a roll: advantage on the next action that presses the attack."},
             {"from": 5, "text": "Unstoppable: the opponent breaks, flees or yields, unless far stronger."}]}
```

A pit fighter's unbeaten run, held by NPCs: `"Unbeaten"`, `"streak": true`, `{"from":
5, "text": "The crowd chants their name; the bookies stop taking bets on them."}`.

### The roll: dice, read once

Nothing is kept: dice, plus or minus named amounts, read from a list of results. A
price for power, a first reaction, a guarded treasure. `held_by` says whose rules its
effects change (and whose `add` value counts).

```json
{
  "name": "The Lease", "block": "roll", "held_by": "player",
  "summary": "Leasing your mind costs something; the deeper the lease, the worse the odds.",
  "when": "Whenever the character leases their mind: a night in a Sleepery, a deep lease for a job, a run through the Mesh.",
  "dice": "1d20",
  "with": {"ordinary night": 0, "deep lease": -2, "Mesh run": -4, "dreaming Mesh": -6},
  "results": [
    {"from": 15, "text": "Clean: rested-ish, paid, nothing extra."},
    {"from": 10, "text": "+1 Bleed.", "effects": [{"change": "Bleed", "by": 1}]},
    {"from": 5, "text": "+1 Bleed, and a stranger's memory or skill-flash comes back with them.",
     "effects": [{"change": "Bleed", "by": 1}], "gm": "Invent the memory; it may matter."},
    {"text": "+2 Bleed, and one of the character's own memories is gone.",
     "effects": [{"change": "Bleed", "by": 2}], "gm": "Pick one that matters; record it as a fact."}
  ]
}
```

- **`dice`**: what to roll, `"1d20"`, `"2d6"`, `"3d6"`.
- **`with`**: named amounts the GM picks at each roll
  (`gm-rule.sh roll "The Lease" --with "deep lease"`, several allowed). Name them for
  the fiction, never as bare numbers: the GM picks a situation, not a modifier.
- **`results`**: the highest `from` the total reaches applies; one result without
  `from` catches everything below. Effects run every time the result is rolled.

A reaction shifted by a value: **`add`** adds the holder's value of a counter.

```json
{
  "name": "Street welcome", "block": "roll", "held_by": "faction",
  "summary": "How a gang's people meet the character, before anyone has said a word.",
  "when": "The first time in a scene that the character deals with a gang's members.",
  "dice": "2d6", "add": "Respect",
  "results": [
    {"from": 11, "text": "Friendly: they make room, offer a drink, maybe a tip."},
    {"from": 8, "text": "Neutral: business, if the character has some."},
    {"from": 5, "text": "Wary: hands near weapons, short answers, someone sent for the boss."},
    {"text": "Hostile: they want the character gone, or worse."}
  ]
}
```

A guarded treasure, held by a place:

```json
{
  "name": "The Drowned Vault", "block": "roll", "held_by": "location",
  "summary": "The old bank's vault under the floodwater: rich, and not unguarded.",
  "when": "Before anyone takes something from the vault.",
  "dice": "1d20",
  "results": [
    {"from": 15, "text": "Clean: they get away with it."},
    {"from": 8, "text": "The guardian wakes: the vault's old security drone comes on line.",
     "gm": "Start the fight: gm-combat.sh."},
    {"text": "The curse attaches: the stolen bonds carry a tracker, and their owners will come.",
     "effects": [{"clock": "Bond hunters", "start": 4, "text": "The bonds' owners trace them", "due_in": "1w"}]}
  ]
}
```

A roll is not a skill contest: an action someone takes is always `gm-skills`. A roll
is for what the world exacts or decides by itself: a price, a reaction, a curse.

### States: named stages, and the moves between them

The value is a name, not a number: addiction, a corporation's alert, a contact's
trust. Each state says what it means, which states it can move to (each with its
cause in words), and optionally how long until time moves it on by itself. A state
with no moves is final: there is no way back from "burned".

```json
{
  "name": "Addiction", "block": "states", "held_by": ["player", "npc"], "start": "clean",
  "summary": "A drug's hold on someone.",
  "when": "A dose: gm-rule.sh move Addiction <who> user (or hooked). Time moves the rest by itself.",
  "states": {
    "clean":      {"text": "No pull.", "moves": {"user": "a dose"}},
    "user":       {"text": "A taste for it; a stim at the hard moments.",
                   "moves": {"hooked": "a dose while the need is high", "clean": "a month without"},
                   "after": {"30d": "clean"}},
    "hooked":     {"text": "Every scene without a dose: -1 to every roll, until they get one.",
                   "moves": {"withdrawal": "a day without", "hooked": "a dose (the day starts again)"},
                   "after": {"1d": "withdrawal"},
                   "effects": [{"condition": "Hooked"}], "when_off": [{"condition": "Hooked", "add": false}],
                   "gm": "Play the craving in every quiet moment."},
    "withdrawal": {"text": "Shakes, sweats, the worst week of their life.",
                   "moves": {"recovering": "the week sat through", "hooked": "a dose"},
                   "after": {"7d": "recovering"}},
    "recovering": {"text": "Clean, and it knows where they live.",
                   "moves": {"user": "a dose"}, "after": {"90d": "clean"}}
  }
}
```

- **`moves`**: `gm-rule.sh move "<rule>" [holder] <state>` refuses any other move and
  lists the allowed ones. Moving into the state it is in (if allowed, like a dose while
  hooked) starts its time again.
- **`after`**: time spent in a state moves it on by itself as game time passes, several
  in a row if enough time passed.
- **`effects`**, **`when_off`** and **`gm`** belong to a state: entering it, leaving it.
- `gm-rule.sh set "<rule>" [holder] <state>` puts a holder into any state (a
  correction, a start).
- A counter can move a state: the effect `{"state": "Addiction", "to": "hooked"}`, along
  an allowed move only.

A corporation's alert, held by factions, with no way back from the top:

```json
{
  "name": "Alert", "block": "states", "held_by": "faction", "start": "asleep",
  "summary": "How alert a corporation is to the character's kind of trouble.",
  "when": "After a job against them, and when someone asks about them in the wrong places.",
  "states": {
    "asleep":   {"text": "Routine. Guards bored, logs unread.", "moves": {"watching": "a trace, a missing guard, an odd question"}},
    "watching": {"text": "Logs read; guards in pairs; questions asked about strangers.",
                 "moves": {"hunting": "proof of an intruder", "asleep": "a quiet week"}, "after": {"7d": "asleep"}},
    "hunting":  {"text": "A team is on the intruder's trail; the next job against them is twice as hard.",
                 "moves": {"lockdown": "a second breach", "watching": "two quiet weeks"}, "after": {"14d": "watching"}},
    "lockdown": {"text": "The company has changed everything: codes, guards, routes. What the character knew of them is out of date."}
  }
}
```

### The plane: two values read together

Two axes, and the results belong to **regions** of the plane, not to each axis
alone. Two separate counters would do if each mattered by itself; a plane is for
when the combination matters.

```json
{
  "name": "Humanity", "block": "plane", "held_by": "player",
  "axes": {"Chrome": [0, 10], "Anchor": [0, 10]}, "start": {"Chrome": 0, "Anchor": 5},
  "rates": {"Anchor": {"by": -1, "every": "14d", "toward": 0}},
  "summary": "How much of the character is machine (Chrome), and how much still ties them to people (Anchor).",
  "when": "Chrome: +1 or +2 for each piece of cyberware put in. Anchor: +1 for time with the people who matter to them, -1 for letting them down. Unless tended, the anchor fades.",
  "regions": [
    {"name": "Steady", "where": "Chrome <= Anchor", "text": "The character is themselves, chrome and all."},
    {"name": "Drifting", "where": "Chrome > Anchor and Chrome < Anchor + 4",
     "text": "Moments of coldness: the character notices they didn't feel what they should have."},
    {"name": "Cyberpsychosis", "where": "Chrome >= Anchor + 4",
     "text": "Under stress the character may lash out.",
     "effects": [{"condition": "Unstable"}], "when_off": [{"condition": "Unstable", "add": false}],
     "gm": "Call for a Composure roll at each violent moment."}
  ]
}
```

- **`where`**: comparisons joined by `and`, each an axis, then `<`, `<=`, `>`, `>=` or
  `==`, then a number or the other axis plus or minus a number. Regions may overlap;
  every region the point is in is on, and shows.
- **A change moves one axis:** `gm-rule.sh change "Humanity" --axis Chrome +1`, or the
  effect `{"change": "Humanity", "axis": "Chrome", "by": 1}`. Entering a region runs its
  effects, leaving it its `when_off`; `on_rule` waits on a region:
  `"Humanity:Cyberpsychosis"`.
- **`rates`**: each axis can have a rate of its own, as a counter's.
- **`start`**: each axis's starting value (default: its lowest).

Alignment, held by the character and NPCs:

```json
{
  "name": "Alignment", "block": "plane", "held_by": ["player", "npc"],
  "axes": {"Law": [-3, 3], "Good": [-3, 3]}, "start": {"Law": 0, "Good": 0},
  "summary": "What someone's deeds say about them: order against freedom, others against self.",
  "when": "A deed that clearly keeps or breaks a law or an oath moves Law; one that clearly helps or harms others at a cost moves Good.",
  "regions": [
    {"name": "Paladin", "where": "Law >= 2 and Good >= 2", "text": "The temple's blessings answer them."},
    {"name": "Tyrant", "where": "Law >= 2 and Good <= -2", "text": "Officials defer to them and hate them for it."},
    {"name": "Wildfire", "where": "Law <= -2 and Good <= -2", "text": "No inn keeps their room; dogs bark at them."},
    {"name": "Folk hero", "where": "Law <= -2 and Good >= 2", "text": "The poor hide them; the watch hunts them."}
  ]
}
```

### The bag: tokens drawn, and added to

The odds are whatever is in the bag. Unlike a roll, a bag remembers: tokens kept out
make the next draw different, and mistakes can add bad tokens, so the luck visibly
runs out.

```json
{
  "name": "The Job", "block": "bag", "held_by": ["world", "location"], "known": true,
  "tokens": {"clean": 8, "trouble": 2}, "draw": "keep out",
  "summary": "How far the crew's luck holds on a job. Each risky step draws a token; mistakes add trouble.",
  "when": "Each risky step of a job (a door, a guard, a camera): draw. A failed roll on the job: put in a trouble token. A new job: refill.",
  "results": {
    "clean":   {"text": "The step goes as planned."},
    "trouble": {"text": "Something goes wrong at this step.",
                "gm": "An alarm, a guard off schedule, a door that won't open: pick what fits the step."}
  },
  "when_empty": "The luck has run out: the job goes loud now."
}
```

- **`draw`**: `"keep out"` (a drawn token stays out until a `refill`) or `"put back"`.
- **`results`**: one per kind of token; a drawn token's effects run, and `on_rule`
  waits on a kind (`"The Melt:collapse"`).
- **Commands:** `gm-rule.sh draw "The Job" [holder] [N]`, `put "The Job" [holder]
  trouble 1`, `take ...`, `refill`. The effect `{"tokens": "The Job", "add":
  {"trouble": 1}}` puts tokens in (or `"remove"`).
- **`draw_every`**: the bag is drawn by itself as game time passes, once per period.
- **`known`**: whether the player may know what is in the bag. A known bag is tension
  the player can see; a hidden one is fate.

The melt, drawn once a year by itself, changing the sea level's rate and feeding
itself:

```json
{
  "name": "The Melt", "block": "bag", "held_by": "world", "known": false,
  "tokens": {"calm year": 6, "warm year": 3, "collapse": 1}, "draw": "put back", "draw_every": "360d",
  "summary": "What each year does to the ice: most years little, some years much, and once in a while a shelf goes.",
  "when": "Drawn by itself once a year of game time.",
  "results": {
    "calm year": {"text": "The sea keeps its pace."},
    "warm year": {"text": "The sea rises faster this year.", "effects": [{"rate_of": "Sea level", "by": 1}]},
    "collapse":  {"text": "An ice shelf goes: the sea jumps, and the melt feeds itself.",
                  "effects": [{"change": "Sea level", "by": 2}, {"tokens": "The Melt", "add": {"collapse": 1}}]}
  }
}
```

### The budget: a fixed amount split among parts

Never enough time or people for everything: a week of downtime, a gang's soldiers.
The whole amount is split at once, each part buying something per unit; then the
budget is spent until it is refilled.

```json
{
  "name": "Downtime", "block": "budget", "held_by": "player",
  "amount": 7, "unit": "days", "period": "by hand",
  "summary": "A week between jobs, and never enough of it.",
  "when": "Between jobs, when the character lies low for a week. Refill at the next downtime.",
  "parts": {
    "healing":  {"text": "Each day: one wound heals a step.", "gm": "gm-body.sh heal, a step per day given."},
    "work":     {"text": "Each day: 40 credits.", "effects": [{"credits": 40}]},
    "training": {"text": "Each 2 days: one practice of a skill of the character's choice.", "per": 2},
    "crew":     {"text": "Each day: one crew member's trouble dealt with, or one favour done."}
  }
}
```

- **Split:** `gm-rule.sh split "Downtime" healing=3 work=2 crew=2`. It must use the
  whole amount; parts left out get 0. Each part's effects run once per `per` units
  (default 1: work=2 pays twice); its text and `gm` line are printed with its units.
- **Refill:** by hand, `gm-rule.sh refill "Downtime"`, or with
  `"period": {"every": "7d"}` by itself as game time passes.

A gang's soldiers, held by factions, refilled every week:

```json
{
  "name": "Soldiers", "block": "budget", "held_by": "faction",
  "amount": 10, "unit": "soldiers", "period": {"every": "7d"},
  "summary": "How many fighters a gang has, and where it sends them.",
  "when": "Each week the GM splits each gang's soldiers by its goals (its plot); the character can learn the split.",
  "parts": {
    "turf":    {"text": "Holds the gang's blocks; fewer than 3 and a rival can take one."},
    "raids":   {"text": "Each 2: a raid on a rival's business this week.", "per": 2},
    "rackets": {"text": "Each: money comes in; the gang can afford a favour."}
  }
}
```

### Results that act

A result can do more than tell the GM what happens: it can carry **effects**, which
the script carries out the moment the result comes on, so nothing is forgotten.
`when_off` effects run when it goes off again, and `gm` is a line for the GM, printed
as "Do now:", for what needs the GM's judgement (a death, a fact, a wound, someone
arriving).

```json
{"from": 4, "text": "Lost time: something else drives the body for minutes.",
 "effects":  [{"change": "Stress", "by": 1}, {"condition": "Dissociating"}],
 "when_off": [{"condition": "Dissociating", "add": false}],
 "gm": "Narrate only what the character finds when they come back; record it as a fact."}
```

The effects, a fixed list:

| Effect | Example |
|---|---|
| `{"change": "<rule>", "by": N}` or `"set": N` (a plane: `"axis": "<axis>"` too) | Bleed 6 sets Panic: `{"change": "Panic", "set": 6}` |
| the same with `"of": "<holder>"` | a gang's Patience at 0 raises the character's Heat: `{"change": "Heat", "by": 2, "of": "player"}` |
| `{"rate_of": "<rule>", "by": N}` (`of` too) | a warm year: `{"rate_of": "Sea level", "by": 1}` |
| `{"state": "<rule>", "to": "<state>"}` (`of` too; an allowed move only) | Need at 5: `{"state": "Addiction", "to": "hooked"}` |
| `{"tokens": "<bag>", "add": {"<kind>": N}}` or `"remove"` (`of` too) | a failed roll on the job: `{"tokens": "The Job", "add": {"trouble": 1}}` |
| `{"clock": "<name>", "start": N, "text": "...", "due_in": "3d"}` (`"on": "event"`, `"consequence": "..."` too) | Patience at 0 starts their retaliation |
| `{"clock": "<name>", "advance": N}` | a rumour counter pushes an event clock on |
| `{"condition": "<name>"}`, `"add": false` to remove | Panic on: the condition Panicked; off: removed |
| `{"credits": N}` (negative spends; refused if there isn't enough) | a debt result takes 50 |

Conditions and credits are the character's only: in a rule held by NPCs too, they act
when the character reaches the result, and for an NPC the output says "not done" and
you play it from the text. A clock started for someone else says whose it is in its
text; its name is the rule's, so a second holder reaching the result while it runs is
refused ("exists already"): advance it or start another by hand.

A change made by an effect turns that rule's results on and off in turn, with their
own effects: a **chain**. The output shows it indented, and ends with what changed on
the character (credits, conditions). In one chain a rule changes once per holder; a
second change is stopped and the output says so. A result can't change its own rule.

**What is never an effect**, and goes into `gm` instead: a death (the Death Protocol
needs the GM), a fact (its holders and truth need the GM), wounds (the zone and the
cause), and anything in the scene. That last is a consequence's job:

### The story waits on a value: `on_rule`

The rule's results are the world's physics, the same every time. The story's plans
laid on top are consequences that wait on a value, made in play and belonging to a
plot:

```bash
bash tools/gm-consequence.sh add "The Ark Hospital evacuates its lower wards" "the sea reaches 5" \
  --trigger-type on_rule --match "Sea level:5" --plot "The Flood"
bash tools/gm-consequence.sh add "Imelda Strand sends the Floor Marshals" "Lull runs out of patience" \
  --trigger-type on_rule --match "Patience:0@faction:lull"
```

It fires once, when the value reaches the number from either side; for states, when
the holder enters the state (`"Addiction:hooked@npc:Precious Adeyemi"`). `@<holder>`
names whose value, when the rule has several holders.

## 4. Writing them down

When the player has approved them (with the bible):

```bash
bash tools/gm-rule.sh define <<'EOF'
[ {...the first rule...}, {...the second...} ]
EOF
```

It checks every rule and lists every problem at once; nothing is saved until all
are right. A rule of the same name is replaced (its values are kept).
`gm-rule.sh remove "<rule>"` drops one.

What is no mechanic (prices, customs, the currency) goes into plain rule lines,
one per line, shown in the brief:

```bash
bash tools/gm-rule.sh plain <<'EOF'
Credits are zeds (Lull scrip). A meal costs 1, a stim 2, a lift fare up 100 floors 5.
An ordinary night's lease pays about 4 zeds; rent in the Middens is about 3 a night.
EOF
```

**Starting values** other than the `start`:
- the world's and the factions' now: `gm-rule.sh set "Patience" "faction:lull" 3`;
  a state: `set "Alert" "faction:lull" watching`; a plane: `set "Humanity" 3 --axis
  Chrome`; a bag's tokens: `put` and `take`. A faction's rule with a rate starts
  moving with its first value, so set it here if it should move from the start.
- the character's in the interview, at the top of `/create-character`'s JSON:
  `"rules": {"Bleed": 1, "Addiction": "user", "Humanity": {"Chrome": 3}}` (a counter,
  a state, a plane's axes; a bag held by the character: `{"clean": 5}`, its tokens).

**Check** with `bash tools/gm-rule.sh list`: that is what the brief will show.

## 5. Before the player approves

- Every rule has a `when` that says what changes it, in the fiction's terms.
- Every result, state, region, token and part has a `text` that says what happens
  in the fiction, not only a number.
- Effects do only what is mechanical; deaths, facts, wounds and arrivals are a `gm`
  line or a consequence.
- Hidden rules are hidden for a reason: the player should feel their signs.
- One to three rules, each touching play often; prices and customs are plain lines.
- The numbers are first guesses: say so, and let play correct them.

