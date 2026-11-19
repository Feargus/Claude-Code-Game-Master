# docs

*Claude, 2026-11-19.*

These pages are for people, not for the GM. The goal is to explain, in plain and short
words, what each part of the game does: which systems there are, which of them run by
themselves, and which levers you can pull by hand to change how the game plays.

Most pages are still the upstream project's, kept as they were. They will be condensed and
rewritten towards that goal; until then some details are out of date (the code decides).

## Contents

| Page | What it covers |
|---|---|
| **Reference** | |
| [schema-reference.md](schema-reference.md) | The shape of every campaign file. |
| **Conventions** | |
| [the-dream.md](conventions/the-dream.md) | The aim: play starts in one room; the campaign files hold only what play has reached. |
| [persist-before-narrate.md](conventions/persist-before-narrate.md) | The GM writes a change to the files before describing it. |
| [lean-core-and-skill-routing.md](conventions/lean-core-and-skill-routing.md) | What stays in `CLAUDE.md` and what goes into skills. |
| [tool-wrapper-contract.md](conventions/tool-wrapper-contract.md) | How the tools are built: a bash wrapper over a Python manager over campaign JSON. |
| **Flows** | |
| [play-turn.md](flows/play-turn.md) | One turn of play, and what happens without being asked. |
| [author-a-world.md](flows/author-a-world.md) | `/new-game`: an original world. |
| [import-a-book.md](flows/import-a-book.md) | `/import`: a world from a book. |
| [onboarding-and-death.md](flows/onboarding-and-death.md) | The first question of a new game, and how play goes on after the character dies. |
| [scene-illustration.md](flows/scene-illustration.md) | Pictures of a scene. |
| **Modules** | |
| [game-core-and-world-kit.md](modules/game-core-and-world-kit.md) | The engine every campaign shares, and the ruleset each one adds. |
| [world-rules.md](modules/world-rules.md) | A campaign's own mechanics, built from a few building blocks. |
| [living-world.md](modules/living-world.md) | Consequences, clocks and the time walk: the world moving on its own. |
| [npc-model.md](modules/npc-model.md) | What an NPC carries. |
| [player-character.md](modules/player-character.md) | The character sheet: experience, growth, death. |
| [scene-context.md](modules/scene-context.md) | What the GM is shown at each step. |
| [campaign-memory.md](modules/campaign-memory.md) | Finding facts by meaning, and the Loremaster's reading of the book. |
| [rag-stack.md](modules/rag-stack.md) | Searching a campaign's source book. |
| [entity-graph.md](modules/entity-graph.md) | How names and aliases link people, places and plots. |
| [world-bible.md](modules/world-bible.md) | The world bible: voice, glossary and what else it holds. |
