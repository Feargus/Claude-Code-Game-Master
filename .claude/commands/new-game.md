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

Run the questionnaire with **AskUserQuestion**. Ask for: a one-line **premise**
(free text — "Conan but on a drowned coast"), **tone**, **magic level**, and
**setting type** (reuse the classic options). Then ALWAYS ask the **genre bend** —
the single most important anti-generic lever:

Also ask the **voice** question — *"Whose voice should this world be narrated in?"*
— with genre-adaptive suggestions + free text (e.g. sword-and-sorcery → Robert E.
Howard; high fantasy → Tolkien / Le Guin; sci-fantasy → Gibson; whimsical →
Pratchett). Store as `voice_exemplar`. This is what makes narration read like a
real author instead of a generic narrator.

Genre bend options:

- *Sword-and-sorcery (Conan):* magic = blood/curse-priced and villainous; bronze-age
  tech; decadent kingdoms vs. barbarian frontier.
- *High fantasy (Tolkien):* deep lineage/ancestry; a pantheon + old songs; pastoral
  vs. rising dark.
- *Tech / sci-fantasy:* nanomagic or charged tech; infrastructure + corporate/clan
  politics.
- *Folk / cosmic horror:* fragile sanity; small community; a wrongness beneath.

Capture the genre bend as a sentence or two of distinct commitments. You do NOT
need a full axis list to sit down — the world's shape emerges at the table.

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
(`style`/`vocab`/`sample_passages`), `tone`, `themes`, `factions`

**Author the `voice` block from `voice_exemplar`** — this is how the GM narrates
in the author's voice at play (surfaced every beat by `get_full_context`):
- `style`: a concrete prose fingerprint imitating the exemplar (sentence rhythm,
  diction, imagery) — not "epic fantasy" but e.g. "Howard's terse, muscular cadence;
  sensory violence; archaic but plain diction."
- `sample_passages`: 2-3 SHORT passages YOU write *in that author's voice* (original
  imitation, NOT copied from the real author's text) so the GM has a concrete target.
- `vocab`: a few signature in-world terms.
Keep geography to the starting street plus a few horizon names. Do not author
the continent. **Wire 2–4 edges** into the `factions`/`geography` graphs (a
tension between two factions, an adjacency between two places) — nodes with no
edges are a cast list, not a world. Signature systems go here — they become the kit.

Validate, then present for approval:
```bash
uv run python lib/world_bible.py validate
uv run python lib/world_bible.py show
```

Show the user the `name`, voice style, themes, factions, and signature systems.
**Gate play on their approval** — let them edit or accept. Then write the kit
and sketch the opening (Phase C). The bible stays `confirmed: false` until they accept.

---

## PHASE C — KIT AND THE OPENING SKETCH (build the one stage)

Write only what tonight needs:

1. Draft the kit: `gm-extract.sh draft-ruleset`. Attributes, rolls and growth are always the repo's (`gm-skills`, `gm-growth`); the world adds its signature systems.
2. Write a short `rules.md` if the world has signature systems.
2b. **Make the signature systems executable — dice, not vibes.** Instantiate 1–3
   `game_core` primitives (**named_track** meter with threshold beats / **price_roll**
   cost for forbidden power / **reaction_roll** reputation-shifted NPC stance /
   **guarded_payoff** guarded-or-cursed treasure), name them for this world, and
   persist: `bash tools/gm-extract.sh write-systems --systems-json '[{"primitive":"named_track","name":"Dread","config":{"max":4,"thresholds":[{"at":4,"consequence":"..."}]}}]'`.
   They surface as YOUR WORLD'S SIGNATURE SYSTEMS and are rolled, not narrated.
2c. **Author the World Index** — a scannable one-sentence roster of the named
   figures, places, relics, and monsters this world contains. There is no book to
   extract from, so **you invent it** from the world's tone/themes (same schema as
   an imported world's index). The GM scans it before inventing a name, so the
   world stays consistent. Persist:
   ```bash
   bash tools/gm-extract.sh write-index --index-json '{"npcs":[{"name":"<Name>","note":"one sentence"}],"locations":[...],"items":[...],"monsters":[...]}'
   ```
   Recognizable, not a gazetteer — the faces the player might actually meet.
3. **Sketch the opening; don't write it yet.** It is written in Phase D with
   `gm-session.sh opening`, once the character exists and the player has said where
   and when to start, so it fits them. Until then nothing of it is stored. Sketch:
   - **the place** you stand in (a street, a room, a deck), with 2–5 **exits** you can see;
   - **2–4 people** there: who they are, how they regard the player, their look and personality, the short names the story
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

When a new name walks on in play: `gm-npc.sh create "<name>" "<role>" "<attitude>" --location "<place>"` or `gm-location.sh add` (with a binder, search it first: `gm-search.sh "<name>" --rag-only`).

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
bash tools/gm-session.sh opening '{
  "time": "<YYYY-MM-DD HH:MM>",
  "place": {"name": "<the place>", "position": "<where it is>", "description": "<…>"},
  "exits": [{"name": "<what you can see>", "aliases": ["<short name>"]}],
  "npcs": [{"name": "<Name>", "who": "<who they are>", "attitude": "<how they regard the player>",
            "aliases": ["<short name>"], "physique": "<…>", "style": "<…>",
            "presence": "<…>", "big_five": "<O1 C0 E2 A-1 N1>", "voice": "<…>"}],
  "plot": {"name": "<the thread>", "type": "main", "description": "<what it is about>",
           "hook": "<the problem that will not wait>",
           "npcs": ["<who it involves, on stage or on the horizon>"],
           "locations": ["<places on its horizon>"]},
  "developments": [
    {"fact": "<the premise, or a secret>", "holders": ["<who knows it>"]},
    {"fact": "<what the antagonist is doing>", "holders": [],
     "clock": {"name": "<the antagonist'"'"'s aim>", "segments": 4, "due_in": "<3d>",
               "consequence": "<what happens in the world when it fills>"}}]
}'
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
gate. **Setting and lore only:** no signature systems, no `ruleset.json`, no
`rules.md`; the campaign plays by the repo's rules (`gm-skills`, `gm-combat`,
`gm-growth`). New mechanics only come from the Together way.

1. **Name the world** from the sentence, then create and switch the campaign
   (Phase A's commands). If the name exists, pick another.
2. **Seed:** write `world-seed.json` as in Phase A, every field chosen by you: the
   sentence is the `premise`; tone, setting, genre bend, voice, art style and
   chronicler fit it.
3. **Bible:** write `world-bible.json` as in Phase B, with `"confirmed": true` and
   `"signature_systems": []`, and validate it. Don't present it for approval.
4. **World index:** Phase C step 2c. Skip steps 1, 2 and 2b (kit, rules, systems).
5. **Sketch the opening** (Phase C step 3), and choose the start yourself: don't
   ask where or when.
6. **Phase D:** lock the chronicler, then tell the player in two lines what world
   they're in. Then the `/create-character` interview (someone of their own, or
   someone from your sketch; fast or slow), then the opening with
   `gm-session.sh opening`, and play.

---

## COMPLETION CHECKLIST (play tonight)
- [ ] `world-seed.json` (premise, voice, art style)
- [ ] `world-bible.json` approved and confirmed (voice + signature systems, not a planet)
- [ ] `ruleset.json` drafted, with the world's signature systems
- [ ] chronicler locked (`gm-image.sh chronicler`)
- [ ] handed off to the one question and the `/create-character` interview (`gm-player.sh create`)
- [ ] the opening written with `gm-session.sh opening` (one place, exits, the people there,
      the plot and its hook, the premise and secrets, the antagonist's clock, the start time)

## Growing the world AT THE TABLE (the real "long-term planning")
You do not pre-plan the campaign — you plan it as you run it. When you see a
long-game opportunity, seed it with the living-world tools and let it tick:
- **Threat clocks** (`gm-clock.sh`) — named pressure that advances on its own.
- **Story threads** (`gm-session.sh end --open-thread`) — questions left hanging.
- **Plots** (`plots.json`) — a spine you extend when the story earns a next beat.
- **Consequences** (`gm-consequence.sh add`) — a seed that fires on the right trigger.
These are how the world develops mid- to long-term — reactively, from play, not
from a gazetteer built before anyone sat down.

## ERROR RECOVERY
- Campaign exists → switch / rename / recreate.
- Bible fails validation → fix the missing required key, re-validate before play.
- `prepare` finds no text → confirm the `authored-canon.md` binder is non-empty.
