#!/usr/bin/env python3
"""A Claude Code hook (PreToolUse, Bash): the output of `bash tools/gm-*` is read whole.

The tools' output is short and written for the GM: every line after the first is
something to act on (docs/conventions/output.md). A model tends to cut it all the
same (`| head -1`, `| tail -2`, `>/dev/null`), a habit from coding work, and then
misses what mattered. This refuses such a command before it runs (exit code 2:
Claude Code shows the GM the reason), so the GM runs it again whole. Other
commands are left alone.

Reads the hook's JSON on standard input; set in `.claude/settings.json`.
"""

import json
import re
import sys

TOOL = re.compile(r"tools/gm-[\w-]+\.sh")
CUT = re.compile(r"\|\s*(head|tail)\b|>\s*/dev/null")
REASON = ("[ERROR] The output of bash tools/gm-* is read whole: nothing of this command "
          "ran; run it again without | head, | tail or >/dev/null. The output is short "
          "and written for you; what follows the first line is what you need to act on.")


def cuts_tool_output(command: str) -> bool:
    """Whether a part of `command` (split at ;, &&, || and line ends) runs one of
    the tools, by its path or through a variable holding it ("N=tools/gm-note.sh;
    bash $N ..."), and cuts what follows it: a pipe into head or tail, or a
    redirect to /dev/null."""
    names = re.findall(r"\b(\w+)=[\"']?(?:\S*/)?tools/gm-[\w-]+\.sh", command)
    calls = [TOOL] + [re.compile(r"\$\{?" + re.escape(n) + r"\b") for n in names]
    for part in re.split(r";|&&|\|\||\n", command):
        for call in calls:
            found = call.search(part)
            if found and CUT.search(part, found.end()):
                return True
    return False


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0
    command = (event.get("tool_input") or {}).get("command") or ""
    if cuts_tool_output(command):
        print(REASON, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
