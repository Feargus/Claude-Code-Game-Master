"""Two Claude Code sessions playing two campaigns don't switch each other's."""

import subprocess
from pathlib import Path

from lib.campaign_manager import CampaignManager

TOOLS = Path(__file__).resolve().parent.parent / "tools"


def test_each_session_keeps_the_campaign_it_switched_to(isolated_world_state, monkeypatch):
    for name in ("salt", "idle"):
        (isolated_world_state / "campaigns" / name).mkdir()
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "session-a")
    CampaignManager().set_active("salt")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "session-b")
    CampaignManager().set_active("idle")

    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "session-a")
    assert CampaignManager().get_active() == "salt"
    shell = subprocess.run(["bash", "-c", f'source "{TOOLS}/common.sh"; get_active_campaign'],
                           capture_output=True, text=True)
    assert shell.stdout.strip() == "salt", shell.stderr

    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")      # no session: the shared one, the last switch
    assert CampaignManager().get_active() == "idle"
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "session-c")   # never switched: the shared one
    assert CampaignManager().get_active() == "idle"
