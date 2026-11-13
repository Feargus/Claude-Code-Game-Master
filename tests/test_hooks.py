"""Tests for the hooks: the config is valid (statusLine preserved), the scripts
parse, and the SessionEnd backup commits the campaigns to their own repository."""

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_settings_keeps_statusline_and_adds_hooks():
    s = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert "statusLine" in s, "must not clobber the existing statusLine"
    assert "Stop" in s["hooks"]
    assert "SessionEnd" in s["hooks"]


def test_hook_scripts_exist_and_parse():
    for name in ("session-autosave.sh", "session-backup.sh"):
        p = ROOT / ".claude" / "hooks" / name
        assert p.exists(), f"missing hook {name}"
        assert subprocess.run(["bash", "-n", str(p)]).returncode == 0


def _git(repo, *words):
    return subprocess.run(["git", "-C", str(repo), *words], capture_output=True, text=True)


def _backup(base, *words):
    import os
    env = {**os.environ, "GM_WORLD_STATE_BASE": str(base)}
    return subprocess.run(["bash", str(ROOT / "tools" / "gm-backup.sh"), *words],
                          capture_output=True, text=True, env=env)


def test_backup_commits_the_campaigns_and_nothing_else(tmp_path):
    """The campaigns folder is a link into its own repository: a new campaign was
    left untracked there until someone added it by hand (Tidewater Ghosts)."""
    repo = tmp_path / "campaign-repo"
    (repo / "campaigns" / "old").mkdir(parents=True)
    (repo / "campaigns" / "old" / "facts.json").write_text("{}")
    (repo / "notes.md").write_text("one")
    (repo / ".gitignore").write_text("campaigns/*/skill-contest.log\n")
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "T")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "start")

    base = tmp_path / "world-state"
    base.mkdir()
    (base / "campaigns").symlink_to(repo / "campaigns")
    (base / "active-campaign.txt").write_text("new")
    (repo / "campaigns" / "new").mkdir()
    (repo / "campaigns" / "new" / "facts.json").write_text("{}")
    (repo / "campaigns" / "new" / "skill-contest.log").write_text("dice")
    (repo / "notes.md").write_text("two")            # the user's own, unfinished

    out = _backup(base, "session ended")
    assert out.returncode == 0 and "committed" in out.stdout
    assert _git(repo, "log", "-1", "--format=%s").stdout.strip() == "Play: new, session ended"
    committed = _git(repo, "show", "--name-only", "--format=").stdout.split()
    assert committed == ["campaigns/new/facts.json"]
    assert _git(repo, "status", "--short").stdout.strip() == "M notes.md"

    assert "nothing new" in _backup(base).stdout
    assert _git(repo, "rev-list", "--count", "HEAD").stdout.strip() == "2"


def test_backup_without_a_repository_does_nothing(isolated_world_state):
    out = _backup(isolated_world_state)
    assert out.returncode == 0 and "not in a git repository" in out.stdout
