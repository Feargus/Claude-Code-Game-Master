# The World Bible

*Claude, 2026-11-19: kept from the upstream docs, not yet rewritten.*

`world-bible.json` is what makes playing Dune feel like Dune rather than d20-fantasy in a
desert. It is authored once (drafted from the book by `gm-extract.sh draft-bible` on
`/import`, written from the seed on `/new-game`) and then read constantly: the **voice**
block reaches the model every beat. The world's own rules are not in the bible: they are
the ruleset's ([the world's own rules](world-rules.md)).

## Half deterministic, half authored — and the seam is the point

`draft_bible` (`lib/book_bible.py:163`) writes only what the source can prove: the
verbatim-filtered voice block and the skeleton keys `validate_bible` demands. It also
scaffolds an empty `index` — the named-thing roster, four buckets (`npcs`, `locations`,
`items`, `monsters`), each entry a `{"name","note"}` pair with a one-sentence note (a
later ticket populates it; the drafter only lays the empty structure). `tone`, `themes`,
`factions` and `geography` are the **model's** authorship, merged in
by re-running the same verb with `--fields-json`. That is why the verb is idempotent:
scaffold, read the book, merge, merge again.

As of 2026-08-15 the bible no longer persists a `chapters` array. `draft_bible` used to
write one derived from `segment_into_chapters`; it stopped, in favor of the `index`. The
splitter itself is untouched — see "Chapter segmentation is shared" below.

It refuses to touch a bible whose `confirmed` flag is absent or true
(`lib/book_bible.py:173`) — the same rule `WorldBible.is_confirmed` reads, so a
hand-authored or approved bible can never be flattened by a re-import.

## The bible is upstream of the rules

The world's own rules go into `ruleset.json` with `gm-rule.sh define`, after the player
approved them with the bible. Every world plays by this fork's rules, and a book's magic
is one of the world's own rules, not spell slots. See [game core and the world's
rules](game-core-and-rules.md).

## Voice is grounded by a verbatim filter

`draft_voice` keeps a sample passage **only if it appears verbatim in the source text**
(`lib/book_bible.py:113-114`). This is the mechanism that stops an imported book's voice
from being the model's impression of the author instead of the author. Two consequences:

- A near-miss passage — reflowed whitespace, smart quotes, an OCR artifact — is silently
  dropped. An empty `sample_passages` after a voice pass usually means the passages were
  paraphrased or the text was normalized, not that the book has no voice.
- `/new-game` worlds have no source text to check against, so their voice block is
  authored rather than filtered.

## The confirm gate blocks fresh drafts only

`is_confirmed()` returns `True` when the flag is **absent** (`lib/world_bible.py:85`).
That default is the whole design: hand-authored and legacy bibles are playable
immediately, and only a freshly auto-drafted bible carrying `confirmed: false` is held
for human review. A campaign with no bible at all is playable — that is the `/new-game`
path before consolidation.

The gate is closed by a person, not by the pipeline: `world_bible.py review` prints the
draft and `world_bible.py confirm` stamps it, and both `/import` and `/new-game` put a
human between them. Nothing in the runtime confirms a bible on its own.

`validate_bible` requires `name`, `voice`, `tone`, `themes`, `factions`, `geography`,
with factions and geography shaped as graphs. Missing keys fail
validation but do **not** block play; only the confirm flag does.

## Chapter segmentation is shared, and prefers real markers

`segment_into_chapters` still lives in `lib/book_bible.py`, but as of 2026-08-15 it feeds
only [the coarse index](rag-stack.md) (`lib/rag/coarse_index.py:47`) — it no longer
populates the bible. It needs **two or more** chapter markers before it will split on them
(`lib/book_bible.py:41`); with fewer, the entire book becomes one span, then gets cut into
20,000-character windows. A PDF whose chapter headings didn't survive extraction therefore
yields arbitrary windows with first-line titles — still usable for retrieval, useless for
citing "chapter 4".

## Related

- [Importing a book](../flows/import-a-book.md) — where the bible is drafted and confirmed
- [Authoring a world](../flows/author-a-world.md) — where it is written from a seed instead
- [Scene context](scene-context.md) — how the voice block reaches the model
