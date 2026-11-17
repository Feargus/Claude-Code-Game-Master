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
  A counter (that it comes back by itself is a rate: a later block, see §5).
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

Built so far: **the counter**, with results that act. The others (a roll, a plane, a bag, a budget,
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
  "range": [0, 10], "start": 2,
  "summary": "How far the sea has risen into the city since the ice shelves went.",
  "when": "+1 for each great storm; +1 a season, at the GM's word, when time passes.",
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
  "range": [0, 5], "start": 5,
  "summary": "How much more a faction will put up with from the character before it acts.",
  "when": "-1 for each slight: a missed payment, a refused job, a member embarrassed. +1 for each week of good behaviour.",
  "results": [
    {"from": 0, "to": 1, "text": "Warnings: a visit, a broken window, a message through a friend."},
    {"from": 0, "to": 0, "text": "They act: the GM starts a clock for their retaliation."}
  ]
}
```

A counter held by places and NPCs:

```json
{
  "name": "Heat", "block": "counter", "held_by": ["location", "npc"],
  "range": [0, 10], "start": 0,
  "summary": "How much attention a place or a person has from the law after trouble.",
  "when": "+2 for a fight, +4 for a death; -1 for each quiet day.",
  "results": [
    {"from": 3, "text": "Patrols pass by more often; the locals are tight-lipped."},
    {"from": 7, "text": "A checkpoint; faces are scanned; the law asks questions by name."}
  ]
}
```

An implant's hidden flaw, held by the character, revealed when a clinic scans it:

```json
{
  "name": "Cascade", "block": "counter", "held_by": "player", "known": false,
  "range": [0, 5], "start": 0,
  "summary": "The cheap arm from Doc Ferro has a firmware fault that is slowly getting worse.",
  "when": "+1 every ten days or so, at the GM's word; +1 when the arm takes a hit. A clinic's scan reveals it: gm-rule.sh reveal Cascade.",
  "results": [
    {"from": 2, "text": "A tremor in the left hand at bad moments: -1 to fine work with it."},
    {"from": 4, "text": "The arm locks for a moment under strain: a failed roll with it fumbles."},
    {"from": 5, "text": "The arm dies. Until it is replaced, it is dead weight."}
  ]
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
| `{"change": "<rule>", "by": N}` or `"set": N` | Bleed 6 sets Panic: `{"change": "Panic", "set": 6}` |
| the same with `"of": "<holder>"` | a gang's Patience at 0 raises the character's Heat: `{"change": "Heat", "by": 2, "of": "player"}` |
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

The other blocks of the plan, for when they are built: **a roll** (dice plus or
minus named amounts, read from a table: a price for power, a first reaction, a
guarded treasure), **a plane** (two values read together: chrome against anchor,
law against good), **a bag** (tokens drawn, odds that change: a job's luck, the
years of the melt), **a budget** (a fixed amount split: downtime days, a gang's
soldiers), **states** (named stages with allowed moves: addiction, a corporation's
alert), and the options **rate** (a value that moves by itself with time),
**hysteresis**, **overflow** (lasting marks) and **streak**. With them come the
effects `rate_of` (change a rate), `tokens` (add to a bag) and `state` (move a state).
