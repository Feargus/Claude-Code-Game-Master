# Book search

*Claude, 2026-11-19: kept from the upstream docs, not yet rewritten.*

Two independent retrieval paths over the same book. They do not share an index.

| | **Pieces** | **Chapter index** |
|---|---|---|
| Unit | pieces of about 1,500 characters, cut at headings and paragraphs (`RAGExtractor.DEFAULT_CHUNK_SIZE`) | whole chapters |
| Storage | the campaign's `vectors/`: `chunks.json` (the texts) and `book.npz` (the vectors, 16-bit) | rebuilt in memory per instance, never persisted |
| Embeddings | EmbeddingGemma-300m, the facts' model (`lib/embedder.py`, through the helper process) | **none by default** (see below) |
| Returns | passage text, with cosine distances | pointers `{index, title, score}` |
| Feeds | `/enhance`, `gm-search --rag-only`, scene passages | [the Loremaster](campaign-memory.md) |

## Indexing (rebuilt 2026-11-16)

`gm-extract.sh prepare` (from `/import`) extracts the text, cuts it into pieces and stores
them in seconds; a background job (`vector_store.index_job`: one at a time, a lock) embeds
them, saving every 10, so it resumes where it stopped. About 4 s per piece on a Raspberry
Pi 4: 15 to 30 minutes for a novel (the test book, *The Hound of the Baskervilles*, 373,000
characters, 303 pieces), longer for a big module.

**Nothing that needs the index uses a half-done one.** `/import` waits for it
(`gm-extract.sh wait`, up to 9 minutes a call, run again while it says so), and the readers
refuse a half-indexed book with what to do: the search (`entity_enhancer.py`), the scene
passages and the Loremaster.

**A book is indexed once.** The finished index is kept in `world-state/book-index/<key>/`
(the key: the book's text and how it is cut; not in git), and a later campaign from the
same book copies it in seconds.

Pieces are embedded as documents and questions as queries (the model's own prompts). A
search compares the question with every piece directly: a few thousand take milliseconds,
so there is no database (this replaced chromadb and sentence-transformers). Distances are
cosine distances, 1 − similarity, as before, so `entity_enhancer.py`'s thresholds stand.

The pieces were 3,000 characters before: the model reads at most 512 tokens per text, so a
quarter of each was lost.

## The whole stack is optional, and its absence is quiet

`lib/rag/__init__.py` checks whether semantic recall is installed (the `recall` extra and
the model files) and sets `RAG_AVAILABLE`. Callers degrade rather than fail (see
[scene context](scene-context.md)): a campaign with no book, semantic recall not installed,
and a query that finds nothing look alike from outside. `gm-recall.sh status` tells them apart.

## The chapter index finds chapters by meaning, keywords as the fallback

The Loremaster (`gm-lore.sh`) finds the chapter a place belongs to, then reads it whole. By
meaning since 2026-11-16: the 12 indexed pieces closest to the question vote for the
chapters they lie in (their similarity added up), so it needs no index of its own, and a
chapter longer than the model reads is no problem. On the test book, "the swamp where
ponies sink" finds Chapter 7 (the pony in the Grimpen Mire) by meaning and Chapter 3 by
keywords. Keywords (word overlap, no model) are the fallback when the campaign's book has
no index or semantic recall isn't installed; a half-indexed book is refused. The brief says
which ran (`found_by`).

## Query templating is the anti-D&D lever

`_template()` appends `"scene character atmosphere setting"` for literary content and
`"stat block rules mechanics encounter"` for game modules. Without it, retrieval over a
novel drifts toward stat-block vocabulary. The content type is a **parameter with a
`"literary"` default** — nothing infers it from the campaign, so a module import gets
literary templating unless the caller says otherwise.

## Enhancement drops rather than pads

Wrong neighbours are worse than a thin sheet. An entity whose retrieved passages never
name it gets **nothing attached** — reported as low-relevance, not written as enhanced.
When that share of a batch is at or above `LOW_RELEVANCE_WARN_FRACTION` (0.25 of total),
the summary prints a WARNING banner, lists the 0-name-bearing names, and the process
exits non-zero. Retrieval queries with the entity's type, not the name alone.

## Related

- [Importing a book](../flows/import-a-book.md) — where vectorization happens in the pipeline
- [Scene context](scene-context.md) — how passages reach a beat
