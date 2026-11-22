# The tool wrapper contract

*Claude, 2026-11-19: kept from the upstream docs, not yet rewritten.*

Three layers, no exceptions: **`tools/gm-*.sh` → `lib/*.py` → per-campaign JSON**. The
wrapper resolves the interpreter and the campaign; the manager holds the logic; state lives
on disk as plain JSON under `world-state/campaigns/<name>/`.

Always invoke as `bash tools/gm-<tool>.sh <command>`, never the Python directly — the
wrapper is what supplies the campaign resolution below.

## What `common.sh` guarantees before a manager runs

Every wrapper sources it, and inherits:

- **`PYTHON_CMD`** — `uv run python` if `uv` is on PATH, else `python3`, else `python`.
  This is why project instructions say never to call bare `python`: the wrapper already
  chose, and choosing differently skips the venv.
- **Path anchoring** — `PROJECT_ROOT` is derived from the script's own location, and
  `common.sh` then **`cd`s there**, so tools work from any working directory. Deriving the
  root is not enough on its own: with no `GM_WORLD_STATE_BASE` in the environment the
  Python side falls back to the *relative* path `world-state`, which resolves against
  whatever directory the caller was in — `cd /tmp && bash <repo>/tools/gm-note.sh
  categories` reported no active campaign and left a stray `/tmp/world-state/` behind. The
  `cd` is what closes that, for every wrapper at once. Because it moves the process,
  `common.sh` first saves the caller's directory as **`CALLER_PWD`**: any verb taking a
  path argument must resolve a relative one against **two anchors, in order** —
  `CALLER_PWD` first, then `PROJECT_ROOT` — and only then report it missing, naming both
  places it looked. Both anchors are real: a human types a path relative to their own
  directory, while a *tool* emits one relative to the project root every wrapper now
  stands in. A tool that emits a `world-state/campaigns/<name>/authored-canon.md`
  binder and pipes it straight into `gm-extract.sh prepare <document>` (today's only
  such verb) would, with `CALLER_PWD` as the sole anchor, fail from every directory but
  the repo root.
- **`WORLD_STATE_BASE`** — `$PROJECT_ROOT/world-state`, unless `GM_WORLD_STATE_BASE` is
  set in the environment, which wins. That env var is the isolation seam: the Python side
  honours it too (`resolve_world_state_base`, `lib/campaign_manager.py`) whenever a manager
  is constructed without an explicit directory, so exporting it moves a whole wrapper +
  manager run onto another world-state tree. Tests that drive the real wrappers point it at
  a tmp tree instead of mutating the player's live campaign.
  The `cd` sharpens the trap on the other side of that seam: a manager that BYPASSES
  `resolve_world_state_base` (as `AgentExtractor` did — it takes its default raw) resolves
  `world-state` to the **live** tree no matter what the environment says.
  `lib/agent_extractor.py` did exactly that and wrote whole campaigns
  into the developer's world-state during tests, so the rule is that a wrapper hands its
  manager the base explicitly — `--world-state "$WORLD_STATE_BASE"` (`gm-extract.sh`)
  or a `$CAMPAIGN_DIR` built from it.
- **`require_active_campaign`** — multi-campaign support is a single file,
  `world-state/active-campaign.txt`. Every tool reads it; nothing takes a campaign
  argument by default. It is the ONLY campaign guard (`gm-extract.sh`'s `require_campaign`
  is a name *resolver* — explicit-arg-else-active — not a guard copy): wrapper-local copies drift out of
  sync with it (three once did, and kept telling the player to run `/new-game` when the
  real fix was `gm-campaign.sh switch`), so the failure text lives in `common.sh` and names
  both repairs — activate a campaign on disk, or start a fresh adventure. A wrapper adds
  only its own routing around the call: usage and mistyped verbs answer BEFORE the guard so
  a typo reports itself as a typo (`gm-session.sh`), and a verb that legitimately runs
  pre-activation takes an explicit campaign name in any argument position instead
  (`gm-extract.sh`'s campaign-named verbs).

## Output is text, for the GM

What a command prints, and how, is in [output.md](output.md). There is no machine format:
`--json` was removed on 2026-11-22 (the GM used it once in about a thousand tool calls,
and of 29 commands checked, 8 accepted it but printed text and 10 refused it). Tests call the managers' functions,
or read the campaign files a command wrote. JSON is only ever input
(`cli_output.json_input`: the opening, a beat, a character).

## Input validation is a manager concern, not a wrapper one

`lib/validators.py` holds the shared input guards (names, attitudes, dice notation) that
managers call before writing. The wrapper layer validates almost nothing — `common.sh` has
a `validate_name`, but the real trust boundary is inside the Python. A manager that skips
`Validators` writes whatever it was handed straight to disk.

## Related

- [A play turn](../flows/play-turn.md) — where these calls sit in the loop
- [Persist before narrate](persist-before-narrate.md) — when to call them
- [Output](output.md) — what the commands print
