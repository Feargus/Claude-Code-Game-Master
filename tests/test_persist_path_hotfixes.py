"""Tests for persist-path-hotfixes.

Unrelated leaks on the persist path, fixed together:

1. `gm-note.sh` / `gm-time.sh` resolved both their Python module and `world-state`
   against the caller's working directory, so they blew up (and dropped a stray
   `world-state/` behind them) whenever the GM ran them from anywhere but the
   project root.
2. `kill` still marks a character dead (the corpse guard went with `modify_hp`).

The wrapper tests run the real scripts against a fixture campaign built under
tmp_path, with GM_WORLD_STATE_BASE pointing the whole tool layer at it, so an
interrupted run can no longer leave the player pointing at a deleted fixture.
The single exception is the unpinned foreign-cwd test, which needs the default
resolution to be under test and so reads (only reads) the live tree.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
LIVE_ACTIVE_FILE = PROJECT_ROOT / "world-state" / "active-campaign.txt"
FIXTURE_CAMPAIGN = Path(__file__).parent / "fixtures" / "world-state" / "campaigns" / "dungeon-crawler-carl"

sys.path.insert(0, str(PROJECT_ROOT / "lib"))
from player_manager import PlayerManager  # noqa: E402


@pytest.fixture
def active_fixture_campaign(isolated_world_state):
    """A throwaway copy of the DCC fixture, active inside the tmp world-state."""
    name = "test-persist-path-hotfixes"
    dest = isolated_world_state / "campaigns" / name
    shutil.copytree(FIXTURE_CAMPAIGN, dest)
    (isolated_world_state / "active-campaign.txt").write_text(name + "\n")
    return dest


@pytest.fixture
def foreign_cwd(tmp_path):
    """A working directory that is neither the project root nor the world-state,
    so a wrapper that resolves paths against the caller's cwd is caught here."""
    cwd = tmp_path / "elsewhere"
    cwd.mkdir()
    return cwd


def _run_from(cwd, *args):
    return subprocess.run(
        ["bash", str(PROJECT_ROOT / args[0]), *args[1:]],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=180,
    )


def _live_campaign_with_facts():
    """The live campaign dir, if it exists AND already has a facts.json.

    The unpinned test below is the only one that reaches the live tree, and it
    may only READ it: `gm-time.sh show` prints the game time and writes nothing
    (it reads no facts either, so a live campaign in an older form still does)."""
    if not LIVE_ACTIVE_FILE.exists():
        return None
    name = LIVE_ACTIVE_FILE.read_text().strip()
    campaign = PROJECT_ROOT / "world-state" / "campaigns" / name
    return campaign if name and (campaign / "facts.json").exists() else None


# --- 1. the wrappers work from any working directory --------------------------

@pytest.mark.parametrize("argv", [
    ("tools/gm-note.sh", "recent", "1"),
    ("tools/gm-time.sh", "set", "2187-10-26 19:30"),
], ids=["gm-note", "gm-time"])
def test_wrapper_runs_from_foreign_cwd(active_fixture_campaign, foreign_cwd, argv):
    result = _run_from(foreign_cwd, *argv)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "No module named" not in result.stderr
    assert "No active campaign" not in result.stdout + result.stderr
    # The old failure mode also littered a world-state/ tree in the caller's cwd.
    assert not (foreign_cwd / "world-state").exists()


def test_gm_time_persists_to_the_campaign_from_foreign_cwd(active_fixture_campaign, foreign_cwd):
    assert _run_from(foreign_cwd, "tools/gm-time.sh", "set", "2187-10-26 19:30").returncode == 0
    overview = json.loads((active_fixture_campaign / "campaign-overview.json").read_text())
    assert overview["time_of_day"] == "Dusk"
    assert overview["current_date"] == "Friday, 26 October 2187"


@pytest.mark.skipif(
    _live_campaign_with_facts() is None,
    reason="needs a live active campaign to run the wrappers unpinned",
)
def test_wrapper_runs_from_foreign_cwd_without_the_env_pin(foreign_cwd, monkeypatch):
    """GM_WORLD_STATE_BASE is an ABSOLUTE path, so the pin every other test here
    relies on would keep the wrappers working even if `cd "$PROJECT_ROOT"` were
    deleted from them. Unpinned is the shape the GM actually runs in and the only
    one where the regression bites: without the cd, the manager's default
    "world-state" is relative and resolves against the caller's cwd, so the tool
    reports no active campaign and litters a world-state/ tree behind it.

    This is the one test that reaches the live world-state, and only to read:
    `gm-time.sh show` prints and exits."""
    monkeypatch.delenv("GM_WORLD_STATE_BASE", raising=False)
    before = LIVE_ACTIVE_FILE.read_bytes()
    before_mtime = LIVE_ACTIVE_FILE.stat().st_mtime_ns

    result = _run_from(foreign_cwd, "tools/gm-time.sh", "show")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "No active campaign" not in result.stdout + result.stderr
    assert not (foreign_cwd / "world-state").exists()
    assert LIVE_ACTIVE_FILE.read_bytes() == before
    assert LIVE_ACTIVE_FILE.stat().st_mtime_ns == before_mtime


def test_the_live_world_state_is_never_touched(active_fixture_campaign, foreign_cwd):
    """Isolation itself: running the real wrappers leaves the player's pointer
    unmodified, and creates no campaign under the live tree."""
    before = LIVE_ACTIVE_FILE.read_bytes() if LIVE_ACTIVE_FILE.exists() else None
    before_mtime = LIVE_ACTIVE_FILE.stat().st_mtime_ns if LIVE_ACTIVE_FILE.exists() else None

    assert _run_from(foreign_cwd, "tools/gm-note.sh", "recent", "1").returncode == 0
    assert _run_from(foreign_cwd, "tools/gm-time.sh", "set", "2187-10-26 19:30").returncode == 0

    after = LIVE_ACTIVE_FILE.read_bytes() if LIVE_ACTIVE_FILE.exists() else None
    assert after == before
    if before_mtime is not None:
        assert LIVE_ACTIVE_FILE.stat().st_mtime_ns == before_mtime
    assert not (PROJECT_ROOT / "world-state" / "campaigns" / active_fixture_campaign.name).exists()


# --- 2. kill ------------------------------------------------------------------

def test_kill_marks_the_character_dead(dcc_world):
    mgr = PlayerManager(dcc_world)
    result = mgr.kill_character(cause="the Iron Tangle")
    assert result["success"] and result["status"] == "dead"
    assert mgr._sheet()["status"]["state"] == "dead"
