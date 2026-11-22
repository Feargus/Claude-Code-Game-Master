"""Shared command-line helpers: an error, and JSON given as input.

What the commands print is in docs/conventions/output.md. There is no JSON output
(`--json` was removed on 2026-11-22: the GM reads text, and the tests call the
functions); JSON is only ever input (`json_input`: the opening, a beat, a character).
"""

import json
import sys


def emit_error(message) -> int:
    """Print `[ERROR] <message>` on standard error. Returns 1 so callers can
    `sys.exit(emit_error(...))`."""
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
