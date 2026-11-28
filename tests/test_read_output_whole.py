"""The hook that refuses a command cutting the output of `bash tools/gm-*`
(.claude/hooks/read-output-whole.py). The commands are shapes the GM used in the
What Remains playtest, where a third of the tools' calls were cut."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parent.parent / ".claude" / "hooks" / "read-output-whole.py"


def run(command: str) -> subprocess.CompletedProcess:
    event = {"tool_name": "Bash", "tool_input": {"command": command}}
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(event),
                          capture_output=True, text=True)


@pytest.mark.parametrize("command", [
    'bash tools/gm-note.sh "Ish hid the case." | head -1',
    'bash tools/gm-rule.sh change "The Keel" +2 --axis Thread 2>&1 | tail -4',
    'bash tools/gm-scene.sh enter "Teo Locke" >/dev/null; bash tools/gm-note.sh tell f1 player',
    'bash tools/gm-session.sh header 2>/dev/null',
    'N=tools/gm-note.sh; bash $N "x" | tail -2',
    'L=tools/gm-location.sh\np(){ bash $L presence "$1" aurelian=2 | tail -1; }',
    'for l in "Kettle Yard" "The Open Hand"; do bash tools/gm-location.sh show "$l" | head -12; done',
])
def test_cut_output_of_the_tools_is_refused(command):
    result = run(command)
    assert result.returncode == 2
    assert result.stderr.startswith("[ERROR] The output of bash tools/gm-* is read whole: "
                                    "nothing of this command ran")


@pytest.mark.parametrize("command", [
    "ls",
    'bash tools/gm-note.sh "Ish hid the case."',
    'bash tools/gm-note.sh "x"; ls world-state | head',
    "sed -n 1,80p lib/world_bible.py | head -5",
    'bash tools/gm-note.sh beat <<\'EOF\'\n[{"fact": "She turned her head."}]\nEOF',
    'bash tools/gm-session.sh context 2>&1 | grep -v onnx',
])
def test_everything_else_runs(command):
    result = run(command)
    assert result.returncode == 0 and result.stderr == ""


def test_no_json_is_no_refusal():
    result = subprocess.run([sys.executable, str(HOOK)], input="not json",
                            capture_output=True, text=True)
    assert result.returncode == 0
