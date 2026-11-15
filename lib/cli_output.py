"""Shared CLI output helpers: structured (JSON) vs human-readable tool output.

Managers print human text by default. Passing `--json` (or DM_JSON=1) makes them
emit a stable envelope the model can parse instead of scraping stdout:

    {"ok": true,  "data": <result>}
    {"ok": false, "error": "<message>", "code": <code|null>}

This kills the stdout-scraping + prefix/typo bug classes without adding an MCP
process. Wire incrementally: detect mode with wants_json(), strip the flag before
argparse with strip_json_flag(), and route results through emit()/emit_error().
"""

import json
import os
import sys


def wants_json(argv=None) -> bool:
    """True if --json was passed or DM_JSON=1 is set."""
    argv = sys.argv if argv is None else argv
    return "--json" in argv or os.environ.get("DM_JSON") == "1"


def strip_json_flag(argv=None):
    """Return argv with the --json flag removed (so argparse never sees it)."""
    argv = sys.argv if argv is None else argv
    return [a for a in argv if a != "--json"]


def emit(data=None, message=None, json_mode=False):
    """Emit a success result: a JSON envelope when json_mode, else the human message."""
    if json_mode:
        print(json.dumps({"ok": True, "data": data}, ensure_ascii=False, indent=2))
    elif message is not None:
        print(message)


def emit_error(message, json_mode=False, code=None) -> int:
    """Emit an error. Returns 1 so callers can `sys.exit(emit_error(...))`."""
    if json_mode:
        print(json.dumps({"ok": False, "error": str(message), "code": code}, ensure_ascii=False))
    else:
        print(f"[ERROR] {message}", file=sys.stderr)
    return 1


FROM_STDIN = "-"


def json_input(raw, what: str = "the JSON"):
    """The JSON a command was given, parsed. Given as an argument, or, when the
    argument is left out (or is "-"), written after the command:

        bash tools/gm-note.sh beat <<'EOF'
        [{"fact": "Dolph's hand shook."}]
        EOF

    Between <<'EOF' and EOF nothing needs escaping, apostrophes included (in a
    '...' argument they can't be written, and the GM dropped them). Raises
    ValueError, with what to do, if there is none or it isn't valid JSON."""
    if raw is None or raw in (FROM_STDIN, "--stdin"):
        raw = "" if sys.stdin.isatty() else sys.stdin.read()
    if not str(raw).strip():
        raise ValueError(f"Nothing given for {what}: write the JSON after the command, "
                         f"between <<'EOF' and a line EOF.")
    try:
        return json.loads(raw)
    except ValueError as error:
        raise ValueError(f"{what[:1].upper()}{what[1:]} isn't valid JSON: {error}") from error
