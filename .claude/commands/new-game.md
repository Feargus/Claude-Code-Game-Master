# /new-game - Create Your World

Author tonight's table, not a planet. Same dream as `/import`: kit, voice, one
street. The campaign file is a **journal of where the table has
been**. The world grows AS YOU PLAY — seed a clock, a thread, or a plot when you
see a long-game opportunity, materialize the next face or place when play walks
toward it. Do not pre-build the universe: author tonight's one stage, then let the
living-world tools grow it from the table.

See `docs/conventions/the-dream.md`.

Two ways, as the player chose in `/gm`:
- **Together:** Phases A–D below, a conversation at each step.
- **From one sentence:** QUICK WORLD at the end. The same phases and files, built by
  you without questions, and setting and lore only.

---

## PHASE A — SEED (genre-aware questionnaire)

Create + switch the campaign first:

```bash
bash tools/gm-campaign.sh create "<CAMPAIGN_NAME>"
bash tools/gm-campaign.sh switch "<CAMPAIGN_NAME>"
CAMPAIGN_DIR=$(bash tools/gm-campaign.sh path)
```
(If the name exists: offer switch / rename / recreate.)

Run the questionnaire in plain text, one question at a time: each a numbered list
of **six** suggestions that fit what the player has said so far, each a few words
and a short line, and a last line saying they can answer in their own words. (Not
AskUserQuestion: it holds only four.) Phone-friendly, no box-drawing frames. Ask for:
a one-line **premise** (free text — "Conan but on a drowned coast"), **tone**, **magic
level** (in a world without magic: the tech, and how much chrome is in people), and
**setting type**. Then ALWAYS ask the **genre bend** — the single most important
anti-generic lever:

Also ask the **voice** question — *"Whose voice should this world be narrated in?"*
— with genre-adaptive suggestions + free text (e.g. sword-and-sorcery → Robert E.
Howard; high fantasy → Tolkien / Le Guin; sci-fantasy → Gibson; whimsical →
Pratchett). Store as `voice_exemplar`. This is what makes narration read like a
real author instead of a generic narrator.

Genre bend options (examples of the kind: suggest six that fit the premise, a
climate cyberpunk world gets cyberpunk bends):

- *Sword-and-sorcery (Conan):* magic = blood/curse-priced and villainous; bronze-age
  tech; decadent kingdoms vs. barbarian frontier.
- *High fantasy (Tolkien):* deep lineage/ancestry; a pantheon + old songs; pastoral
  vs. rising dark.
- *Tech / sci-fantasy:* nanomagic or charged tech; infrastructure + corporate/clan
  politics.
- *Folk / cosmic horror:* fragile sanity; small community; a wrongness beneath.

Capture the genre bend as a sentence or two of distinct commitments. You do NOT
need a full axis list to sit down — the world's shape emerges at the table.

**The world's own rules.** Load the `gm-rules` skill now. While the player describes
the world (and later their character), listen for what could be a rule of its own (a
pressure that grows, two things pulling against each other, a price for power) and
suggest one to three, each in a plain sentence: "The water level could be a counter
that rises by itself." The player picks, changes or drops them. They are approved
with the bible (Phase B) and written in Phase C.

Write `world-seed.json` to the campaign dir:

```json
{
  "premise": "...", "tone": "...", "magic": "...", "setting": "...",
  "genre_bend": "<the distinct commitments, in a sentence or two>",
  "voice_exemplar": "<author/work to channel, e.g. 'Robert E. Howard'>",
  "art_style": "In the style of <a distinctive, fully-specified look> — a mashup of two unexpected references often lands ('In the style of Frank Miller's Batman but rendered in smudged charcoal', 'In the style of a gilded medieval illuminated manuscript but depicting cyberpunk megacities'), or commit hard to one strong style the world already implies. Either way it must be specific enough that two images read as one artist's hand. This is the campaign's locked gallery signature, set ONCE here.",
  "chronicler_name": "<the in-world artist who 'makes' every image, fits the tone>",
  "chronicler_persona": "<their voice/bias — grim, sarcastic, reverent, unreliable>"
}
```

---

## PHASE B — SKELETON (one pass, while the seed is fresh)

YOU (the main GM agent) author the full creative skeleton NOW, in one pass, while
all the seed context is fresh in mind. This is the world's identity — get it right
here; everything else grows from the table.

Write `world-bible.json` to the campaign dir with `confirmed: false` and ALL
required keys (validated by `lib/world_bible.py`): `name`, `voice`
(`style`/`sample_passages`), `tone`, `themes`, `factions`

**Author the `voice` block from `voice_exemplar`** — this is how the GM narrates
in the author's voice at play (surfaced every beat by `get_full_context`):
- `style`: a concrete prose fingerprint imitating the exemplar (sentence rhythm,
  diction, imagery) — not "epic fantasy" but e.g. "Howard's terse, muscular cadence;
  sensory violence; archaic but plain diction."
- `sample_passages`: 2-3 SHORT passages YOU write *in that author's voice* (original
  imitation, NOT copied from the real author's text) so the GM has a concrete target.
- The world's own words go into `glossary`, a key of the bible beside `voice`: each
  term with a line on what it means here, `{"glossary": {"Lantern papers":
  {"description": "the certificate of a ghost; forged ones are expensive and fragile",
  "plots": []}}}`. A few to start; more join in play (`gm-glossary.sh add`).
**The factions** (3–5 groups with a goal: a gang, a corp, a church, the claimers on
the plain) are records of their own, not part of the bible. Write each one, with a
short id that never changes:
```bash
bash tools/gm-faction.sh create "<name>" --id <short id> --kind "<gang, megacorp…>" \
  --description "<what it is, a sentence or two>" \
  --impulse "<what drives it, a sentence>" --value "<what it stands for or never does>"
```
One to three impulses, one or two values; a value only where the faction really cares.
Keep geography to the starting street plus a few horizon names. Do not author
the continent. **Wire 2–4 ties** between factions, each as one of them sees the other
(`gm-faction.sh tie <id> <other id> "<a tension, in words>"`; a tie can run both ways,
seen differently from each side), and give `geography` a graph of places (nodes and
edges, an adjacency between two places). Groups with no ties are a cast list, not a
world. The bible has no factions: they and their ties are in `factions.json`. The
world's own rules are not in the bible: they go into the ruleset in Phase C.

Validate, then present for approval:
```bash
uv run python lib/world_bible.py validate
uv run python lib/world_bible.py show
bash tools/gm-faction.sh list
```

Show the user the `name`, voice style, themes, factions, and the world's own rules
you suggest, each in a sentence or two with its numbers.
**Gate play on their approval** — let them edit or accept. Then write the kit
and sketch the opening (Phase C). The bible stays `confirmed: false` until they accept.

---

## PHASE C — KIT AND THE OPENING SKETCH (build the one stage)

Write only what tonight needs:

1. Draft the kit: `gm-extract.sh draft-ruleset`. Attributes, rolls and growth are always the repo's (`gm-skills`, `gm-growth`); the world adds its own rules.
2. **Write the world's own rules** as the player approved them, in the formats of the
   `gm-rules` skill: `bash tools/gm-rule.sh define <<'EOF'`, the list, a line `EOF`; what
   is no mechanic (prices, customs) with `gm-rule.sh plain`; starting values of the
   world and the factions with `gm-rule.sh set`. Check with `gm-rule.sh list`: that is
   what the brief will show. The player's starting values come with the character.
2b. **The factions: power, relations and Standing**, in every world, a quick one too.
   Power and relations are the repo's faction rules (`gm-rules`, "The repo's faction
   rules"); Standing is the one rule every world defines. Unset, every power is 3 and
   every relation 0, which makes all factions alike.
   - **Power:** Military, Economic, Political, Covert, 0–10, about 3 on average per
     faction but shaped by what it is: the police strong in Military, weaker in
     Economic; a megacorp rich and political, with little muscle of its own; a street
     church political and poor. `gm-rule.sh set "Military" "faction:<id>" N` for each
     power that isn't 3.
   - **Relation:** every pair with a tie gets the number its words say, −5 open war to
     +5 allies (`gm-rule.sh set "Relation" "<id>+<id>" N`; one value for both sides,
     so a tie seen differently from each side gets the value between them). A pair
     with no tie may stay 0 when nothing is between them; give it a value when the
     descriptions imply one (the police and the gang they raid).
   - A resting point where a faction or pair should drift back, if any
     (`gm-rule.sh rate … --by 1 --toward N`).
   - **Standing**, how each faction regards the character (`gm-rules`, "Standing"):
     define it in the world's words (`gm-rule.sh define`), then for each faction its
     value and the point it rests at (`gm-rule.sh set "Standing" "faction:<id>" N`,
     `gm-rule.sh rate "Standing" "faction:<id>" --toward N`).
   Check with `bash tools/gm-faction.sh show <id>` (Power and Relations) and
   `bash tools/gm-rule.sh list` (Standing).
2c. **Name the world's people, places, creatures and things** — the faces the player
   might actually meet, recognizable, not a gazetteer (about 6–10 people, 4–8 places,
   a few kinds of enemy, a few of the world's own words). There is no book, so **you
   invent them** from the world's tone and themes. Each becomes a record now, a sketch
   to fill in when play walks toward it, so the name check, triggers and plots see it:
   ```bash
   bash tools/gm-location.sh add "<place>" "<where it is>"                  # a bare place: described before it is narrated
   bash tools/gm-location.sh presence "<place>" <faction id>=N ...          # who is around: 0 (never: a rival's HQ) to 5 (they run it)
   bash tools/gm-npc.sh create "<Name>" --background "<one sentence>" --location "<place>" [--faction <id>]   # a sketch; any few fields
   bash tools/gm-mob.sh add "<kind of enemy>" --note "<one sentence>"       # stats before it is fought
   bash tools/gm-glossary.sh add "<term>" "<what it means here>"            # relics, institutions, slang
   ```
   Places first, so people can be usually found there. A name close to one already
   made is refused (one record per person or place).
   **Every person needs a way back into the story on its own:** a usual place
   (`--location`, a bare place is fine: the location card lists them as "usually
   found here" whenever the story goes there), or a part in the opening's clock or
   consequences. A sketch tied only to "when they are in the scene" is forgotten,
   since nothing brings them into the scene.
2d. **Each faction's first plot**, its plan: written from its values and impulses and
   where it stands (power, presence, relations, leader), with its plan clock, the true
   plan as a fact it holds, and its portents, as the `/gm` command file says under "A
   faction's plot". These are the world's own business, going on beside the character;
   the opening's plot (below) may grow out of one.
3. **Sketch the opening; don't write it yet.** It is written in Phase D with
   `gm-session.sh opening`, once the character exists and the player has said where
   and when to start, so it fits them. Until then nothing of it is stored. Sketch:
   - **the place** you stand in (a street, a room, a deck), with 2–5 **exits** you can see;
     each with a sentence or two of what it is like (written before it is narrated);
   - **2–4 people** there: who they are, their attitude towards the player if they have one (adjectives only), their look and personality, the short names the story
     will use (aliases), and where each is usually found;
   - **the plot**: every campaign starts with at least one. Its **hook** is the
     problem that won't wait, and becomes its first beat. Its `npcs` and `locations`
     may name people and places on the horizon that get no record yet;
   - **the premise and the secrets** as facts with who knows them (`holders`; none
     for a secret nobody knows yet), e.g. "Auntie Ro hid the sleeve", held by Ro;
   - **the story's spine: the antagonist's clock.** A stage without a countdown is
     inert. At least one threat clock whose aim completes off-screen whether or not
     the player engages, due when it would come to a head if nobody interferes
     (`3d`, `2w`). One clock, not a doom gazetteer;
   - **the start time** (`YYYY-MM-DD HH:MM`).

4. Optional thin binder: a short `authored-canon.md` of *this street only*, then
   `gm-extract.sh prepare` so RAG has something to pull. Do not author the continent.

When a new name walks on in play: `gm-npc.sh create "<name>" "<role>" ["<attitude: adjectives>"] [--location "<place>"]` or `gm-location.sh add "<place>" "<where>" "<what it is like>"` (with a binder, search it first: `gm-search.sh "<name>" --rag-only`).

---

## PHASE D — HANDOFF (play tonight)

**Lock the chronicler + art style NOW** (the gallery signature is a world-creation
decision, not an in-play improvisation) from the seed's `art_style` /
`chronicler_*` fields:

```bash
bash tools/gm-image.sh chronicler \
  --name "<chronicler_name>" \
  --style "<art_style — MUST start with 'In the style of ...'; a distinctive, fully-specified look>" \
  --persona "<chronicler_persona>"
```

The `scene-illustrator` agent READS this locked style and opens every prompt with
it — it never picks its own. Make it specific enough that two images read as one
artist's hand (a surprising mashup is one way there, not the only one). This single
chronicler record carries BOTH halves of the image identity — the **art style**
(`--style`) and the **art narrator** (`--name` / `--persona`, the in-world entity
who "makes" every picture). Lock both now; they never change in play.

Then display a summary box and hand off:

```
Your world awaits its hero. Who are you in this world?
```

Then run the `/create-character` interview. It asks who the player wants to be:
someone of their own, or **someone from this world**, one of the people in your
sketch (name a few; create that one NPC first with `gm-npc.sh create`, so `--canon`
can find them, and leave them out of the opening's people). It also asks fast or
slow, and saves with `gm-player.sh create`.

**After identity, before you open the scene, ask where/when they want to start**
(in a quick world, choose it yourself).
Offer a fitting default but let them name their own opening — a specific location,
scene, or point in the timeline — and fit the sketch to it.

**Write the opening**, all of it in one call (the fields: `lib/opening.py`). It makes
everything through the normal tools, and keeps nothing if any part is refused:

```bash
bash tools/gm-session.sh opening <<'EOF'
{
  "time": "<YYYY-MM-DD HH:MM>",
  "place": {"name": "<the place>", "position": "<where it is>", "description": "<what it is like>"},
  "exits": [{"name": "<what you can see>", "position": "<where it is>",
             "description": "<what it is like, a sentence or two>", "aliases": ["<short name>"]}],
  "npcs": [{"name": "<Name>", "who": "<who they are>", "attitude": "<attitude towards the player: one or more adjectives, comma separated; leave out if none>",
            "aliases": ["<short name>"], "physique": "<…>", "style": "<…>",
            "presence": "<…>", "big_five": "<O1 C0 E2 A-1 N1>", "voice": "<…>"}],
  "plot": {"name": "<short name, one to four words>", "kind": "main",
           "description": "<what it is about>",
           "hook": "<the problem that will not wait: where it stands at the start>",
           "owner": "<whose goal it is, if anyone's: an NPC>", "goal": "<what they are after>",
           "involves": ["<people and places it involves; each a record already, sketches too>"]},
  "developments": [
    {"fact": "<the premise, or a secret>", "holders": ["<who knows it>"]},
    {"fact": "<what the antagonist is doing>", "holders": [],
     "clock": {"name": "<short name, one to three words>", "text": "<the antagonist's aim>",
               "segments": 4, "due_in": "<3d>",
               "consequence": "<what happens in the world when it fills>"}}]
}
EOF
```

**Give every NPC on the stage a look and a personality** in the opening (the PC gets
theirs at `/create-character`): `physique` (sex, age, ethnicity, build, distinguishing
features), `style` (outfit, aesthetic, scent), `presence` (how they carry themselves),
`big_five` (the Big Five in OCEAN order, each −3 to +3, 0 the average person) and
`voice`; `tells`, `want` and `fears` too if you know them. Ground them in the bible.
Only the people on this stage: the rest get theirs when they walk on
(`gm-npc.sh set "<NPC>" --physique "..." ...`).

Then open the scene from what `opening` printed: the place, who is here, the hook.

---

## QUICK WORLD (from one sentence)

The player gives one sentence about the world. That is the only question about the
world: you build everything else from it, with no questionnaire and no approval
gate. **Setting and lore only:** no rules of its own but `Standing`, which every world
has (step 4); the campaign plays by the repo's rules (`gm-skills`, `gm-combat`,
`gm-growth`). New mechanics only come from the Together way.

1. **Name the world** from the sentence, then create and switch the campaign
   (Phase A's commands). If the name exists, pick another.
2. **Seed:** write `world-seed.json` as in Phase A, every field chosen by you: the
   sentence is the `premise`; tone, setting, genre bend, voice, art style and
   chronicler fit it.
3. **Bible:** write `world-bible.json` as in Phase B, with `"confirmed": true`, and
   validate it. Don't present it for approval.
4. **Factions and world index:** Phase C steps 2b (the factions' power, relations and
   Standing) and 2c. Skip steps 1 and 2 (the kit and the world's own rules).
5. **Sketch the opening** (Phase C step 3), and choose the start yourself: don't
   ask where or when.
6. **Phase D:** lock the chronicler, then tell the player in two lines what world
   they're in. Then the `/create-character` interview (someone of their own, or
   someone from your sketch; fast or slow), then the opening with
   `gm-session.sh opening`, and play.

---

## COMPLETION CHECKLIST (play tonight)
- [ ] `world-seed.json` (premise, voice, art style)
- [ ] `world-bible.json` approved and confirmed (voice, factions, not a planet), with the world's own rules
- [ ] `ruleset.json` drafted, with the world's own rules (`gm-rule.sh list`)
- [ ] chronicler locked (`gm-image.sh chronicler`)
- [ ] handed off to the one question and the `/create-character` interview (`gm-player.sh create`)
- [ ] the opening written with `gm-session.sh opening` (one place, exits, the people there,
      the plot and its hook, the premise and secrets, the antagonist's clock, the start time)

## Growing the world AT THE TABLE (the real "long-term planning")
You do not pre-plan the campaign — you plan it as you run it. When you see a
long-game opportunity, seed it with the living-world tools and let it tick:
- **Threat clocks** (`gm-clock.sh`) — named pressure that advances on its own.
- **Plots** (`gm-plot.sh`) — someone's goal or the problem the story turns on; what belongs to one says so (`--plot`), and its one sentence (`stands`) moves with it.
- **Consequences** (`gm-consequence.sh add`) — a seed that fires on the right trigger.
These are how the world develops mid- to long-term — reactively, from play, not
from a gazetteer built before anyone sat down.

## ERROR RECOVERY
- Campaign exists → switch / rename / recreate.
- Bible fails validation → fix the missing required key, re-validate before play.
- `prepare` finds no text → confirm the `authored-canon.md` binder is non-empty.
