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

- **A pressure that grows:** a debt, a sickness, a city's fear of the character,
  the water rising. A counter.
- **Something that wears down and comes back:** patience, nerve, heat from the law.
  A counter, with a rate if it comes back by itself.
- **A price for power:** what sorcery, a deep lease or a forbidden implant costs.
- **Two things pulling against each other:** chrome against what ties you to
  people; law against freedom.
- **Luck that runs out as things go wrong; never enough time or soldiers for
  everything; a condition with stages and no way back.**

A rule must matter in many scenes. Scenery is not a rule: the city's architecture
belongs in the bible, prices in a plain rule line (§4).

**What a rule is not:** anything the shared rules do. Actions are skill contests,
harm is wounds, deadlines are clocks, how someone feels about the character is an
attitude, who knows what is facts. A rule adds to these and never replaces one.

## 2. Suggesting them

Suggest **one to three** rules, each in one plain sentence, with what it adds to
play:

> "The water level could be a counter for the whole world, 0 to 10: at 3 the Lower
> Docks flood at every tide, at 6 the ring road goes under. It rises when the GM
> says a storm hits."

The player picks, changes or drops them; you can offer two ways of modelling the
same thing. Show the chosen ones with the bible for approval, with their numbers.
Numbers are first guesses: play decides whether they are right.

## 3. The building blocks

Built so far: **the counter** (with a rate, hysteresis, overflow and streaks) and
**the roll**, with results that act. The others (a roll, a plane, a bag, a budget,
states, and the options rate, hysteresis, overflow and streak) come in later steps
(rules-proposal.md in the campaign repo). Until then, model with counters, and put
what a counter can't do into the rule's `notes`: the GM reads them in the brief.

### Every rule

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
| `{"change": "<rule>", "by": N}` or `"set": N` | Bleed 6 sets Panic: `{"change": "Panic", "set": 6}` |
| the same with `"of": "<holder>"` | a gang's Patience at 0 raises the character's Heat: `{"change": "Heat", "by": 2, "of": "player"}` |
| `{"rate_of": "<rule>", "by": N}` (`of` too) | a warm year: `{"rate_of": "Sea level", "by": 1}` |
| `{"clock": "<name>", "start": N, "text": "...", "due_in": "3d"}` (`"on": "event"`, `"consequence": "..."` too) | Patience at 0 starts their retaliation |
| `{"clock": "<name>", "advance": N}` | a rumour counter pushes an event clock on |
| `{"condition": "<name>"}`, `"add": false` to remove | Panic on: the condition Panicked; off: removed |
| `{"credits": N}` (negative spends; refused if there isn't enough) | a debt result takes 50 |

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

It fires once, when the value reaches the number from either side. `@<holder>` names
whose value, when the rule has several holders.

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

**Starting values** other than the `start`: the world's and the factions' now
(`gm-rule.sh set "Patience" "faction:lull" 3`), the character's in the interview
(`"rules": {"Bleed": 1}` in `/create-character`'s JSON).

**Check** with `bash tools/gm-rule.sh list`: that is what the brief will show. Every
rule needs a `when` that says what changes it, and every result a text that says
what happens in the fiction.

## 5. Coming later

The other blocks of the plan, for when they are built: **a plane** (two values read together: chrome against anchor,
law against good), **a bag** (tokens drawn, odds that change: a job's luck, the
years of the melt), **a budget** (a fixed amount split: downtime days, a gang's
soldiers), **states** (named stages with allowed moves: addiction, a corporation's
alert). With them come the effects `tokens` (add to a bag) and `state` (move a
state).
