---
type: Module
title: Recall by meaning, and the Loremaster
description: How the GM finds a fact by what it means (semantic recall over the facts, places and plots), and the cached deep read over a campaign's source book.
sources:
  - { resource: /lib/recall.py }
  - { resource: /lib/embedder.py }
  - { resource: /lib/embedding_store.py }
  - { resource: /lib/loremaster.py }
  - { resource: /tools/gm-recall.sh }
  - { resource: /tools/gm-lore.sh }
---

# Recall by meaning, and the Loremaster

## Recall by meaning (since 2026-11-15)

`gm-note.sh find --like "<question>"` ranks the facts by how close they are to the
question: "have we met a clown?" finds "Pagliacci took off his makeup and wept". It
replaced `gm-recall.sh recall` and `lib/campaign_memory.py` (keyword recall over plots and
facts, and before that session summaries and arc entries).

- **The model** (`lib/embedder.py`): EmbeddingGemma-300m, 4-bit, on ONNX Runtime; no
  PyTorch. Chosen by a benchmark on a Raspberry Pi 4: about 6 s to load, under a second per
  text, 0.5 GB of RAM. Optional (`uv sync --extra recall`, `gm-recall.sh setup`); without it,
  `--like` ranks by keywords (BM25) and says so.
- **The vectors** (`lib/embedding_store.py`): one per fact, place and plot, in the
  campaign's `embeddings.npz` (derived, not in git). Saving `facts.json`, `locations.json`
  or `plots.json` starts a background job when the command ends; one job runs at a time
  (a lock), embeds what is new or changed and exits.
- **The ranking** (`lib/recall.py`): who knows a fact is a hard filter (`--held-by`,
  `--hidden`, `--secret`, `--truth`, `--category`, `--text`); what comes from matching words
  is only a bonus (`--about` +0.10, `--at` +0.05, `--plot` +0.05, recency up to +0.05),
  because those links can be missing. Facts a hard filter removed but that would have
  ranked among the shown ones are named as near-misses, so a gap in the data shows.
- **Suggestions:** `gm-plot.sh add` lists the recorded facts closest to the new plot; once
  play has begun, `gm-npc.sh create` and `gm-location.sh add` refuse a record that reads like
  an existing one (similarity 0.60 or more; a person re-described scored 0.63 to 0.74,
  different people at most 0.65) unless `--another` is given.
- **Notes after a fact** (`lib/recall_notes.py`): the background job compares each new fact
  with the open plots (0.45, clearly the best), the people (0.55, and closer than the
  character and everyone it is linked to) and the consequences waiting on an event (0.50),
  and leaves notes in `embeddings.notes.json`; the next command that needs a campaign prints
  them once (`tools/common.sh`), not into `--json` output. A note acted on meanwhile is dropped.
- **A fact not embedded yet** (the background job is still running) is embedded by the
  query itself, up to 10; beyond that it counts as average.

The design and its decisions: the campaign repo's `recall-proposal.md`.

## The Loremaster re-indexes the whole book per instance

`Loremaster.__init__` loads the campaign's book text and calls `index.build(text)` every
time it is constructed (`lib/loremaster.py:29-31`). There is no persisted index, so
construction cost scales with book size — which is why `gm-lore.sh` is an on-demand call
for new/important scenes, not something wired into every context load. It reads `current-document.txt` or
`book-text.txt` from the campaign directory — both are gitignored, so a cloned campaign
has no book text and every brief comes back with empty chapters.

The gate is the point of the module: a cached location that is not flagged `important`
returns immediately with no read. Two tiers of output (since 2026-08-13):

- **Default** — pointers + a bounded `grounded_excerpt` (`EXCERPT_CHARS`). This is what
  `gm-session.sh move` auto-runs on the **first visit** to a location when the campaign
  retains book text — the cache gates it, so revisits are silent and the deep read fires
  once per place.
- **`--full`** — the same brief plus `chapter_text`, the *entire* chapter span, for the
  long-context read when the GM actually narrates the place. The full text rides the
  return, never the cache — the book file is the storage.

(Until 2026-08-13 the excerpt was 500 chars and nothing returned the full span, so the
"long-context read" the module was built for had no way to happen.)

## Related

- [Scene context](scene-context.md): the start brief and the cards
- [RAG stack](rag-stack.md): the search over a campaign's source book
