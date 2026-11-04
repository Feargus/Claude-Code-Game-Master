# Rust & Chrome: a Cyberpunk Game Master for Claude Code

A solo tabletop RPG run by Claude Code, with homebrew rules and a cyberpunk setting.

> **Work in progress.** This is a heavily modified fork of [Sstobo/Claude-Code-Game-Master](https://github.com/Sstobo/Claude-Code-Game-Master). The D&D rules are gone, replaced by a homebrew system that is still being playtested and changes often. Expect rough edges and breaking changes.

## About

The idea: move one step away from fixed rulebooks towards the LLM's judgment, while dice still decide outcomes.

- **Claude judges.** It reads what you describe and turns it into a roll: which skill, which attributes, how hard, what helps or hinders.
- **The dice decide,** rolled by a script that does all the arithmetic and logs every die.
- **Claude narrates** the result. You never see dice, numbers or difficulties, only what happens to your character.

The game keeps its state on disk (character, NPCs, places, threads, clocks, consequences), so a campaign survives across sessions, and the world keeps moving while you're away.

## What's different from the original

Kept from upstream: the harness itself (Claude Code as the GM, scripts that save state, scene context, threat clocks, consequences, plot threads, book import and recall). Changed or new:

| Area | In this fork |
|---|---|
| **Rolls** | Every roll is a skill contest: nine attributes as die sizes (d6 to d20), 31 skills, advantage and disadvantage per attribute, labeled modifiers, automatic luck. One script, `tools/gm-skill-contest.sh`. |
| **Harm** | No HP. Seven body zones with four wounds each; armor and cyberware absorb hits. `tools/gm-body.sh`. |
| **Time** | A real in-game clock. Moves take time, and threat clocks fill as time passes. |
| **Runs** | Targets of a job (a vault, a corp tower, a computer system) are laid out before you arrive, so exits can't appear just because you need one. |
| **Characters** | Created in a short interview: the GM proposes everything from a one-line concept, you change what you like. Leveling raises attributes and skills, plus improvised perks. |
| **Removed** | D&D 5e: its web API, monster, spell and gear agents, classes, death saves, the "World Kit" rule switch. |

## Requirements

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code)
- Python 3.11 or newer, [uv](https://docs.astral.sh/uv/) and `jq` (the install script sets these up)
- Developed on Linux; macOS should work, Windows is untested.

## Installation

```bash
git clone https://github.com/Feargus/Claude-Code-Game-Master.git
cd Claude-Code-Game-Master
git checkout Towards-Cyberpunk
./install.sh
```

The work happens on the `Towards-Cyberpunk` branch.

## Usage

Start Claude Code in the repo folder and run `/gm`:

```bash
claude
```

```
/gm
```

`/gm` lets you pick a campaign or start a new one (`/new-game` builds a world from a questionnaire, `/import` turns a book into one), then creates your character and starts playing. Useful commands during play:

| Command | What it does |
|---|---|
| `/gm end` | End the session, recording where you paused. Invents nothing. |
| `/gm cliffhanger` | End the session on a cliffhanger. |
| `/gm world` | Let the world move off-screen, e.g. during a long rest. |
| `/gm character` | Show your character sheet. |
| `/gm status` | A short overview of the campaign. |

Campaign data lives in `world-state/campaigns/`, which git ignores: **back it up yourself.**

## How it's organized

| Folder | Contents |
|---|---|
| `CLAUDE.md` | The GM's always-loaded instructions. |
| `.claude/skills/` | The rules, loaded when needed: `gm-skills` (rolls, attributes, skills), `gm-combat` (fights and wounds), `gm-conditions`, `gm-levelup`, `gm-sites`, `gm-social`, `gm-craft` (narration). |
| `.claude/commands/` | The slash commands (`/gm`, `/new-game`, `/create-character`, …). |
| `.claude/agents/` | Helpers the GM starts by itself (plot threads, NPC backstories, site layouts, book extraction). |
| `tools/` | The shell commands the GM runs; each wraps a Python module in `lib/`. |
| `tests/` | The test suite. |
| `docs/` | Design notes from upstream, only partly updated for this fork. |

## Development

```bash
uv sync --extra rag --extra dev   # install test and book-search dependencies
uv run pytest                     # run the tests
```

## Credits

Based on [Claude Code Game Master](https://github.com/Sstobo/Claude-Code-Game-Master) by [Sean Stobo](https://www.linkedin.com/in/sean-stobo/). This fork is maintained by [Feargus](https://github.com/Feargus) and was built with Claude.

## License

Licensed under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/), the same license as the original: free to share and adapt for non-commercial use, with attribution, under the same license. This is a modified version of the original work; see [What's different](#whats-different-from-the-original). See [LICENSE](LICENSE) for details.
