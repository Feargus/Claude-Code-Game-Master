"""The shared command-line helpers (lib/cli_output.py): an error on standard error,
and no JSON output (`--json` removed 2026-11-22: docs/conventions/output.md)."""

import subprocess
import sys
from pathlib import Path

from lib.cli_output import emit_error
from lib.search import WorldSearcher

ROOT = Path(__file__).resolve().parent.parent


def test_an_error_goes_to_standard_error_with_exit_code_1(capsys):
    assert emit_error("boom") == 1
    out = capsys.readouterr()
    assert out.err.strip() == "[ERROR] boom" and out.out == ""


def test_json_is_no_option_any_more(dcc_world):
    """It used to be accepted by every command and honoured by some: recording a
    fact took it and printed text, and a helper built on it broke (the Long Hull)."""
    r = subprocess.run([sys.executable, str(ROOT / "lib" / "note_manager.py"), "recent", "--json"],
                       capture_output=True, text=True, cwd=str(Path(dcc_world).parent))
    assert r.returncode != 0 and "--json" in r.stderr


def test_search_returns_structured_dict(dcc_world):
    results = WorldSearcher(dcc_world).search_all("dragon")
    assert isinstance(results, dict)
    for key in ("facts", "npcs", "locations", "consequences", "plots"):
        assert key in results
