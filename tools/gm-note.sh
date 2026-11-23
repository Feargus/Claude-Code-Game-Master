#!/bin/bash
# gm-note.sh - Record world facts (wrapper for note_manager.py)

source "$(dirname "$0")/common.sh"

usage() {
    echo "Usage: gm-note.sh [add] <fact> [--about <id>]... [--not-about <id>]..."
    echo "                  [--also <id>]... | [--holders <id>]... | [--secret]"
    echo "                  [--truth wrong|partial] [--version-of <fact id>]"
    echo "                  [--at <place> | --nowhere]   where it happened (default: here)"
    echo "                  [--plot <plot>]...           the plot it belongs to"
    echo "                  [--from <npc>]               who said it (what they told, a lie, half of it)"
    echo "       gm-note.sh tell <fact id> <holder>... [--from <npc>]   someone learns it (from whom)"
    echo "       gm-note.sh edit <fact id> \"<text>\"          a new text for it"
    echo "       gm-note.sh remove <fact id>                  recorded by mistake, or twice"
    echo "       gm-note.sh about <fact id> [--add <id>]... [--remove <id>]..."
    echo "       gm-note.sh plot <fact id> [--add <plot>]... [--remove <plot>]..."
    echo "       gm-note.sh truth <fact id> wrong|partial|true [--version-of <id>]"
    echo "       gm-note.sh beat <<'EOF' <json list> EOF     several facts of one beat at once"
    echo "                                                    (version_of \"#1\": an earlier fact of it)"
    echo "       gm-note.sh witness <npc> [--at <place>] [--from T] [--to T] [--include <id>]... [--dry-run]"
    echo "                                                    they were there: they learn what happened"
    echo "       gm-note.sh show <fact id>...                 facts in full (truth, versions)"
    echo "       gm-note.sh find [--held-by <id>]... [--about <id>]... [--secret | --hidden]"
    echo "                       [--truth wrong|partial] [--text \"words\"] [--at <place>] [--plot <plot>] [--limit N]"
    echo "                       [--like \"<question>\"]            ranked by meaning, best first"
    echo "                                                    facts by who knows them, who they're about"
    echo "       gm-note.sh recent [N]                        the last N facts (default 10)"
    echo ""
    echo "A fact is one sentence or two; it has no category."
    echo "about: who or what the fact concerns: player, npc:<name>, location:<name>."
    echo "Names found in the text are added by themselves; --not-about drops a wrong one."
    echo "holders: who knows it. Default: the player and the NPCs present."
    echo "--also adds to it; --holders replaces it (player, npc:<name>, street, public);"
    echo "--secret: nobody. Present = the party and the scene list (gm-scene.sh)."
    echo "A wrong or partial version: --truth wrong|partial [--version-of <fact id>]."
    echo ""
    echo "Example: gm-note.sh \"Wren paid off Dekker\" --about location:Lanternside"
}

if [ "$#" -lt 1 ]; then
    usage
    exit 1
fi

require_active_campaign

# "gm-note.sh add <fact>" is the same as "gm-note.sh <fact>" (an easy guess).
if [ "$1" = "add" ]; then
    shift
fi

case "$1" in
    get)
        # Gone: it printed facts.json raw, without the [SECRET] and [HIDDEN FROM
        # PLAYER] marks.
        echo "[ERROR] gm-note.sh get is gone. Look facts up with:" >&2
        echo "  gm-note.sh recent [N]  |  find --about <id> / --held-by <id> / --plot <plot> / --text \"words\" / --like \"<question>\"  |  show <fact id>" >&2
        exit 1
        ;;
    tell|about|plot|truth|edit|remove|show|find|recent|beat|witness)
        $PYTHON_CMD "$LIB_DIR/note_manager.py" "$@"
        ;;
    *)
        # Anything else is a fact to record. A single word isn't one, and neither
        # is the old form with a category in front: note_manager.py refuses both.
        $PYTHON_CMD "$LIB_DIR/note_manager.py" add "$@"
        ;;
esac
