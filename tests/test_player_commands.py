"""The player's commands take no name: a campaign has one player character.

The name used to be an optional first argument that was ignored, so
`gm-player.sh credits +50` read "+50" as the name, showed the balance and
exited 0: the GM believed the money had moved.
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
