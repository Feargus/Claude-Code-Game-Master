#!/bin/bash
# SessionEnd hook: commit (and push) the campaigns when the Claude session closes,
# so every campaign, new ones included, is in its repository even if the session
# was never ended with /gm end. ADVISORY ONLY — never blocks; always exits 0.
set +e

DIR="${CLAUDE_PROJECT_DIR:-.}"
cd "$DIR" 2>/dev/null || exit 0

bash tools/gm-backup.sh >/dev/null 2>&1

exit 0
