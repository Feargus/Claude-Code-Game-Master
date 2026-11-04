"""Tests for advisory-hooks: PostToolUse state-write logging + Stop autosave.

Hooks are advisory and non-blocking. These assert the config is valid (statusLine
preserved), the scripts parse, and the PostToolUse script exits 0 (never wedges).
"""

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_settings_keeps_statusline_and_adds_hooks():
    s = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert "statusLine" in s, "must not clobber the existing statusLine"
    assert "PostToolUse" in s["hooks"]
    assert "Stop" in s["hooks"]


def test_hook_scripts_exist_and_parse():
    for name in ("post-tool-state-log.sh", "session-autosave.sh"):
        p = ROOT / ".claude" / "hooks" / name
        assert p.exists(), f"missing hook {name}"
        assert subprocess.run(["bash", "-n", str(p)]).returncode == 0


def test_post_tool_hook_never_blocks(tmp_path):
    inp = '{"tool_input": {"command": "bash tools/gm-body.sh hit chest 1"}}'
    r = subprocess.run(
        ["bash", str(ROOT / ".claude" / "hooks" / "post-tool-state-log.sh")],
        input=inp, capture_output=True, text=True,
        env={"CLAUDE_PROJECT_DIR": str(tmp_path), "PATH": __import__("os").environ.get("PATH", "")},
    )
    assert r.returncode == 0
    # It should have logged the state write under the project dir.
    log = tmp_path / ".ship-it" / "state-writes.log"
    assert log.exists() and "gm-body.sh hit" in log.read_text(encoding="utf-8")


def test_post_tool_hook_ignores_non_state_commands(tmp_path):
    inp = '{"tool_input": {"command": "ls -la"}}'
    r = subprocess.run(
        ["bash", str(ROOT / ".claude" / "hooks" / "post-tool-state-log.sh")],
        input=inp, capture_output=True, text=True,
        env={"CLAUDE_PROJECT_DIR": str(tmp_path), "PATH": __import__("os").environ.get("PATH", "")},
    )
    assert r.returncode == 0
    assert not (tmp_path / ".ship-it" / "state-writes.log").exists()
