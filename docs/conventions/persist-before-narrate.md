---
type: Convention
title: Persist before narrate
description: The rule the whole harness exists to enforce — and the honest state of its enforcement, which is advisory.
sources:
  - { resource: /.claude/settings.json }
  - { resource: /.claude/hooks/session-autosave.sh }
generated: { by: claude-opus-5, at: 2026-08-13T13:52:08Z }
---

# Persist before narrate

**Nothing happened until it is written to disk.** Every state change — wounds, XP, credits,
inventory, mood, location, condition, consequence, death — is persisted *before* a word of
narration reaches the player. This is what makes a campaign survive a crash, a context
reset, a week away, or a different machine.

The failure it prevents is specific and expensive: the model narrates a transformative
beat, the context window rolls, and the beat never existed. The player loses something they
watched happen.

## Enforcement is advisory. There is no guard.

This convention is worth recording precisely because **nothing blocks a missed persist.**
One hook is configured in `.claude/settings.json`, and it doesn't gate: `session-autosave.sh`
(`Stop`) runs `gm-session.sh save autosave` when an active campaign exists, and always
exits 0. It is a safety net for state *already written* to `character.json` and friends; it
cannot recover a change that was narrated but never persisted. The discipline is on the
author of the turn. (A `PostToolUse` hook that logged state-writing commands was removed on
2026-11-07: nothing read its log.)

## Ordering inside a beat

Persist-first also fixes ordering *within* the beat, and two cases are called out
explicitly in the project instructions because they are easy to get backwards:

- **Loot is persisted before the loot box is shown.**
- **A death is persisted before it is narrated, and the hand-off menu comes after the
  narration** — see [onboarding and the death hand-off](../flows/onboarding-and-death.md).

## Related

- [The tool wrapper contract](tool-wrapper-contract.md) — the commands that do the persisting
- [A play turn](../flows/play-turn.md) — where this sits in the loop
