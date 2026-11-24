"""The player's commands take no name: a campaign has one player character.

So `gm-player.sh credits +50` moves the money, rather than reading "+50" as a
name and showing the balance with exit 0 (the GM would believe the money had moved).
"""

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _run(world, tool, *args):
    return subprocess.run(["bash", str(ROOT / "tools" / tool), *args], capture_output=True,
                          text=True, env=dict(os.environ, GM_WORLD_STATE_BASE=world))


def _sheet(world):
    path = Path(world) / "campaigns" / "dungeon-crawler-carl" / "character.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _credits(world):
    return _sheet(world)["possessions"].get("credits", 0)


def test_credits_change_with_just_the_amount(dcc_world):
    before = _credits(dcc_world)
    assert _run(dcc_world, "gm-player.sh", "credits", "+50").returncode == 0
    assert _run(dcc_world, "gm-player.sh", "credits", "-5").returncode == 0
    assert _credits(dcc_world) == before + 45


def test_the_old_form_with_a_name_fails_loudly_and_changes_nothing(dcc_world):
    before = _credits(dcc_world)
    for args in (["credits", "Tandy", "+50"], ["xp", "Tandy", "+30"],
                 ["kill", "Tandy", "--cause", "fell"], ["loot", "Tandy", "--credits", "5"]):
        result = _run(dcc_world, "gm-player.sh", *args)
        assert result.returncode != 0, args
    assert _credits(dcc_world) == before
    assert _sheet(dcc_world).get("status", {}).get("state") != "dead"


def test_conditions_take_just_the_condition(dcc_world):
    assert _run(dcc_world, "gm-condition.sh", "add", "grappled").returncode == 0
    assert "grappled" in _sheet(dcc_world)["status"]["conditions"]
    assert "grappled" in _run(dcc_world, "gm-condition.sh", "check").stdout
    old_form = _run(dcc_world, "gm-condition.sh", "add", "Tandy", "poisoned")
    assert old_form.returncode == 1 and "Usage" in old_form.stdout
    assert _run(dcc_world, "gm-condition.sh", "remove", "grappled").returncode == 0
    assert "grappled" not in _sheet(dcc_world)["status"]["conditions"]


def test_spending_more_than_there_is_is_refused(dcc_world):
    """`credits -500` with less than that set the credits to 0, printed "spent 500
    credits" and succeeded, so the GM narrated a purchase that couldn't be paid."""
    before = _credits(dcc_world)
    result = _run(dcc_world, "gm-player.sh", "credits", f"-{before + 1}")
    assert result.returncode == 1
    assert f"has {before} credits, not the {before + 1}" in result.stdout + result.stderr
    assert "CREDITS_SPENT" not in result.stdout and _credits(dcc_world) == before
    assert _run(dcc_world, "gm-player.sh", "credits", f"-{before}").returncode == 0   # all of it
    assert _credits(dcc_world) == 0
    result = _run(dcc_world, "gm-player.sh", "loot", "--credits=-5", "--items", "a key")
    assert result.returncode == 1 and "Loot is a gain" in result.stdout + result.stderr
    assert _credits(dcc_world) == 0 and "a key" not in json.dumps(_sheet(dcc_world).get("items", {}))
