#!/bin/bash
# gm-backup.sh - Commit the campaigns to the git repository that holds them
#
#   gm-backup.sh ["note"] [--no-push]
#
# The campaigns folder (world-state/campaigns) is usually a link into a
# repository of its own, whose history is the backup. This commits everything
# under it, new campaigns included, as "Play: <active campaign>[, <note>]", and
# pushes if that repository has a remote branch to push to. Only the campaigns
# folder is committed: other changes in that repository are left alone.
#
# It never fails a session: no repository, nothing new or no network just prints
# a line. Run by the SessionEnd hook and by `gm-session.sh end`.

source "$(dirname "$0")/common.sh"

NOTE=""
PUSH=true
for arg in "$@"; do
    case "$arg" in
        --no-push) PUSH=false ;;
        *) NOTE="$arg" ;;
    esac
done

REAL=$(cd -P "$CAMPAIGNS_DIR" 2>/dev/null && pwd -P) || { echo "Backup: no campaigns folder."; exit 0; }
if ! git -C "$REAL" rev-parse --show-toplevel >/dev/null 2>&1; then
    echo "Backup: the campaigns are not in a git repository; nothing committed."
    exit 0
fi
if git -C "$REAL" check-ignore -q "$REAL" 2>/dev/null; then
    echo "Backup: the campaigns folder is ignored by its repository; nothing committed."
    exit 0
fi

git -C "$REAL" add -A -- . 2>/dev/null
if git -C "$REAL" diff --cached --quiet -- . 2>/dev/null; then
    echo "Backup: nothing new in the campaigns."
else
    MESSAGE="Play: $(get_active_campaign)"
    [ "$MESSAGE" = "Play: " ] && MESSAGE="Play"
    [ -n "$NOTE" ] && MESSAGE="$MESSAGE, $NOTE"
    if git -C "$REAL" commit -q -m "$MESSAGE" -- . 2>/dev/null; then
        echo "Backup: committed the campaigns ($MESSAGE)."
    else
        echo "Backup: the commit failed (run git status in $REAL)."
        exit 0
    fi
fi

if $PUSH && git -C "$REAL" rev-parse --abbrev-ref '@{u}' >/dev/null 2>&1; then
    if [ -n "$(git -C "$REAL" log '@{u}..' --oneline 2>/dev/null)" ]; then
        if timeout 30 git -C "$REAL" push -q 2>/dev/null; then
            echo "Backup: pushed."
        else
            echo "Backup: not pushed (no network?); the next backup tries again."
        fi
    fi
fi
exit 0
