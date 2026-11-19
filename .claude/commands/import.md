# /import — Step into a book

The book **is** the adventure. Index it. Ask who they came to be. Open that page.
Do not scrape Hyboria into a wiki first.

The dream: a holodeck door and a 1983 D&D table. Someone they love is already in
the room. The rest of the book stays on the GM's chair until play walks toward it.

See `docs/conventions/the-dream.md`.

## Usage

```
/import <file-path> [campaign-name]
```

**Arguments:**
- `file-path` — PDF, DOCX, TXT, or MD
- `campaign-name` — optional (defaults to a sane name, never the OceanofPDF filename)

---

## Step 1: Get the file

If arguments weren't provided, check `source-material/`:

```bash
ls -la source-material/ 2>/dev/null | grep -E '\.(pdf|docx|txt|md)$'
```

List what you found, or ask them to drop a file / paste a path. Then ask for a
campaign name (or pick a short one from the title — `conan`, not the dump filename).

---

## Step 2: Put the book on the shelf

This is the only expensive, once-per-book step. Local embeddings. No LLM census.

```
Reading the book and putting it on the shelf...
```

```bash
bash tools/gm-extract.sh prepare "<file-path>" "<campaign-name>"

# REQUIRED here — every RAG read resolves against the ACTIVE campaign.
bash tools/gm-campaign.sh switch "<campaign-name>"

EXPECTED=$(uv run python lib/campaign_manager.py slugify "<campaign-name>")
ACTIVE=$(bash tools/gm-campaign.sh active)
ACTIVE_SLUG=$(uv run python lib/campaign_manager.py slugify "$ACTIVE")
if [ "$ACTIVE_SLUG" != "$EXPECTED" ]; then
    echo "MISMATCH — active is '$ACTIVE', expected '$EXPECTED'" >&2
    exit 1
fi
CAMPAIGN_DIR=$(bash tools/gm-campaign.sh path)
```

**If this block exits non-zero, STOP.** Do not draft a bible. Do not build a stage.

Then wait until the book is indexed. It is indexed in the background (about 15 to 30
minutes for a novel on a Raspberry Pi; seconds if this book was indexed for an earlier
campaign), and nothing that searches it runs before:

```bash
bash tools/gm-extract.sh wait "<campaign-name>"
```

It waits up to 9 minutes. While it says "Still indexing", tell the player how far it is
in a line, and run it again; go on only when it says the book is indexed.

The book is now searchable. That is enough of a "world" to start.

---

## Step 3: The door, not the gazetteer

Do **not** launch extractor agents yet (they only list the book's names, Step 5.5). Do **not** preview entity counts. Do **not**
ask "what should I extract?"

Ask, in the book's tone:

**Who are you in this world — or who did you come to meet?**

Two doors (same as `/gm` identity-first):

- someone from the book (name a few you can actually find via RAG — Conan, Bêlit, Valeria…)
- someone of their own

They came for the fantasy of talking to a favorite character. Spend the spike on
that, not on ability scores and not on a loading screen.

Then, before you build the stage, ask **one more** question — where/when they want
to begin:

**Where — or when — do you want to start?** Offer a fitting default (an iconic
opening scene for this book/character) but make it plain they can name their own:
a specific location, a particular moment or scene from the source, or a point in
the character's timeline ("the night Bêlit dies," "before he was king," "the sack
of such-and-such city"). Build Step 5's opening around **that** start, not the
book's default first page.

---

## Step 4: World identity (tone, not inventory)

Draft the bible, kit, voice, and chronicler so the holodeck *sounds* like the book.
This is identity. It is not a census.

```bash
bash tools/gm-extract.sh draft-bible --name "<World/Book Name>"
```

Read large spans of `current-document.txt` (the chapters that carry the world's
voice). Merge authorship:

```bash
bash tools/gm-extract.sh draft-bible --fields-json <<'EOF'
{
  "tone": "...",
  "themes": ["..."],
  "geography": {"nodes": [{"id":"maul","name":"The Maul"},{"id":"tower","name":"Elephant Tower"}], "edges": [{"from":"maul","to":"tower","adjacency":"across the temple quarter"}]}
}
EOF
uv run python lib/world_bible.py validate
```

The factions are records of their own, not part of the bible (`gm-faction.sh create
"Thieves of the Maul" --id thieves --kind "guild" --description "…" --impulse "…"
--value "…"`, then `--id yara` for the Priesthood of Yara), and so are their ties
(`gm-faction.sh tie yara thieves "preys on them"`, `gm-faction.sh tie thieves yara
"fears them"`).

Keep factions/geography as a **handful of horizon names**, not a gazetteer — but
**wire 2–4 ties and edges** (a tension between two factions, an adjacency between two
places). Nodes with no edges are a cast list, not a world; a couple of real
relationships (the villain's faction vs the player's, the caravan vs the hunt)
pay off in every scene. Do not build a full relationship map.

Attributes are always the nine from `gm-skills`, actions are skill contests, and growth is `gm-growth`'s.

```bash
CAMPAIGN_DIR=$(bash tools/gm-campaign.sh path)
[ -f "$CAMPAIGN_DIR/ruleset.json" ] || bash tools/gm-extract.sh draft-ruleset
```

```bash
CAMPAIGN_DIR=$(bash tools/gm-campaign.sh path)
uv run python lib/overview_seed.py "$CAMPAIGN_DIR" --fields-json <<'EOF'
{"campaign_name": "<World>", "genre": "...", "tone": {"grim": 40, "adventure": 40, "horror": 20}}
EOF
```

**The book's own rules.** Load the `gm-rules` skill. Model what the book's world
runs on (a menace that grows, a price for sorcery, a city's patience) with its
building blocks: one to three rules, each a plain sentence for the player, who
approves them with the bible. Then write them:

```bash
bash tools/gm-rule.sh define <<'EOF'
[{"name": "Menace", "block": "counter", "held_by": "player", "range": [0, 6],
  "summary": "How much the city has come to fear the character.",
  "when": "+1 for each killing seen in public, +2 for a noble's.",
  "results": [{"from": 3, "text": "Men step aside for the character; nobody meets their eye."},
              {"from": 6, "text": "The city turns out to hunt them."}]}]
EOF
bash tools/gm-rule.sh plain <<'EOF'
<a rule line that is no mechanic: prices, customs>
EOF
bash tools/gm-rule.sh list
```

Voice — verbatim excerpts only (the filter drops paraphrase):

```bash
bash tools/gm-extract.sh draft-bible --voice-json <<'EOF'
{
  "style": "...",
  "sample_passages": ["<verbatim 1>", "<verbatim 2>"]
}
EOF
uv run python lib/world_bible.py validate
uv run python lib/world_bible.py review
```

Ask them: **looks right — play it** / **change something**.
`uv run python lib/world_bible.py confirm` only after they say so.

Chronicler (once):

```bash
bash tools/gm-image.sh chronicler \
  --name "<in-world artist>" \
  --style "In the style of ..." \
  --persona "..."
```

---

## Step 5: Build the STAGE — only this room

After they pick a door, read the book for **that** opening. Persist nothing else.

A stage is:

- **1 location** you can stand in (a room, a deck, an alley — not a kingdom)
- **2–4 exits** you can see from here (names + connections; do not fully build the destinations)
- **2–4 people** in this room
- **0–2 objects** in hand or in reach
- **1 hook** that will not wait until morning

```bash
bash tools/gm-search.sh --rag-only "<character or opening scene>" 8
bash tools/gm-lore.sh "<place>" --important
```

Create the PC first: the `/create-character` interview, with the answer to who they
are (someone from the book, or their own concept), fast or slow as the player chooses. Save with
`bash tools/gm-player.sh create` with the JSON after it (`<<'EOF'`, the JSON, a line `EOF`), adding `--canon "<NPC name>"` for someone from
the book; that one NPC is created first (`gm-npc.sh create`, from what the book says),
and stays out of the opening's people.

Then write the opening, before narrating, in one call (the fields: `lib/opening.py`).
It makes the place, exits and people through the normal tools, and keeps nothing if any
part is refused. **Every campaign starts with at least one plot:** its `hook` is the
problem that will not wait and becomes its first beat; its `npcs` and `locations` may
name people and places on the horizon that get no record yet.

**Give the story a spine — the antagonist's clock.** A stage without a countdown is
inert. At least one development carries a threat clock whose aim completes off-screen
whether or not the player engages — the book's looming danger (Yara's sorcery, the
caravan fleeing the city, the cult's ritual). It is due when the aim would complete if
nobody interferes (`3d`, `2w`): one clock, grounded in the book's plot, not a gazetteer
of doom.

```bash
bash tools/gm-session.sh opening <<'EOF'
{
  "time": "<YYYY-MM-DD HH:MM>",
  "place": {"name": "<this room, not a kingdom>", "position": "<where it is>",
            "description": "<what it is like, from the book>"},
  "exits": [{"name": "<what you can see from here>",
             "description": "<what it is like, a sentence or two>"}],
  "npcs": [{"name": "<Name>", "who": "<who they are, in the book>", "attitude": "<attitude towards the player: one or more adjectives, comma separated; leave out if none>",
            "aliases": ["<short name the story uses>"], "physique": "<…>", "style": "<…>",
            "presence": "<…>", "big_five": "<O1 C0 E2 A-1 N1>", "voice": "<…>"}],
  "plot": {"name": "<short name, one to four words>", "kind": "main",
           "description": "<what it is about>",
           "hook": "<the problem that will not wait: where it stands at the start>",
           "owner": "<whose goal it is, if anyone's: an NPC>", "goal": "<what they are after>",
           "involves": ["<people and places it involves; each a record already, sketches too>"]},
  "developments": [
    {"fact": "<what is true here that the book establishes>", "holders": ["<who knows it>"]},
    {"fact": "<what the antagonist is doing>", "holders": [],
     "clock": {"name": "<short name, one to three words>", "text": "<the antagonist's aim>",
               "segments": 4, "due_in": "<3d>",
               "consequence": "<what happens in the world when it fills>"}}]
}
EOF
```

When play walks toward a new name: `gm-search.sh "<name>" --rag-only` for what the book
says, then `gm-npc.sh create` or `gm-location.sh add`.

Enhance **only** the people in this room (so they speak in the book's words):

```bash
bash tools/gm-enhance.sh query "<Name>"
bash tools/gm-enhance.sh apply "<Name>"
```

Do **not** run `gm-enhance.sh batch`. The one use of the `index-extractor` agent
is the light roster below — sketches, not a gazetteer. A name with only a sketch
means not on stage yet.

---

## Step 5.5: Name the book's people, places, creatures and things (sketches, NOT a census)

A light roster of the named things that actually exist in this book, so the GM
reaches for real names (Yara, the Elephant Tower, Yag-kosha) instead of inventing
generic ones. Each becomes a bare record, a sketch filled in when play walks
toward it. No full records, no stats.

Spawn the `index-extractor` agent over the campaign's chunk files
(`chunks/chunk_NNN.txt`) — **hard cap 6 agents, and state that 6-agent cap INSIDE
each prompt**. Give each one kind (`npcs`, `locations`, `items` or `monsters`) and
the chunks to read (split a long book's chunks between agents of the same kind).
Each answers with a JSON list of `{name, note}`, the note ONE sentence, named
things only. Merge the lists by name, then make one record per entry, places first:

```bash
bash tools/gm-location.sh add "<place>" "<where it is, from the book>"          # bare: described before it is narrated
bash tools/gm-npc.sh create "<Name>" --background "<the note>" --location "<place>" # a sketch
bash tools/gm-mob.sh add "<creature>" --note "<the note>"                         # stats before it is fought
bash tools/gm-glossary.sh add "<item or term>" "<the note>"                       # relics, institutions, the book's words
```

A name close to one already made is refused: give the existing record an alias
(`gm-npc.sh alias`) if the book uses both names for one person.
   **Every person needs a way back into the story on its own:** a usual place
   (`--location`, a bare place is fine: the location card lists them as "usually
   found here" whenever the story goes there), or a part in the opening's clock or
   consequences. A sketch tied only to "when they are in the scene" is forgotten,
   since nothing brings them into the scene.

Also put the book's own words (the voice's terms) into the glossary, one line each.

---

## Step 6: Open the door

Narrate the room. Let them talk. One beat. The book is right there — `gm-context.sh`
and `gm-search.sh --rag-only` when someone new walks on. Persist that one new face
or place, then keep playing.

The campaign JSON is a journal of where you've been. Grow it from the table.

---

## Done

```
The book is on the shelf. The door is open.
```

Hand off to `/gm`. Do not present a second menu. Identity already happened.
