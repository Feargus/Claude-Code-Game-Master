#!/bin/bash
# gm-note.sh - Record world facts (wrapper for note_manager.py)

source "$(dirname "$0")/common.sh"

usage() {
    echo "Usage: gm-note.sh [add] <category> <fact> [--about <id>]... [--not-about <id>]..."
    echo "                  [--also <id>]... | [--holders <id>]... | [--secret]"
    echo "                  [--truth wrong|partial] [--version-of <fact id>]"
    echo "                  [--at <place> | --nowhere]   where it happened (default: here)"
    echo "       gm-note.sh tell <fact id> <holder>...      someone learns it"
    echo "       gm-note.sh about <fact id> [--add <id>]... [--remove <id>]..."
    echo "       gm-note.sh truth <fact id> wrong|partial|true [--version-of <id>]"
    echo "       gm-note.sh beat '<json list>'               several facts of one beat at once"
    echo "                                                    (version_of \"#1\": an earlier fact of it)"
    echo "       gm-note.sh witness <npc> [--at <place>] [--from T] [--to T] [--include <id>]... [--dry-run]"
    echo "                                                    they were there: they learn what happened"
    echo "       gm-note.sh show <fact id>...                 facts in full (truth, versions)"
    echo "       gm-note.sh find [--held-by <id>]... [--about <id>]... [--secret | --hidden]"
    echo "                       [--truth wrong|partial] [--category C] [--text \"words\"] [--at <place>] [--limit N]"
    echo "                                                    facts by who knows them, who they're about"
    echo "       gm-note.sh recent [N]                        the last N facts (default 10)"
    echo "       gm-note.sh categories"
    echo ""
    echo "Categories: session_events, plot_local, plot_regional, plot_world,"
    echo "            player_choices, npc_relations, lore, rules"
    echo ""
    echo "about: who or what the fact concerns: player, npc:<name>, location:<name>."
    echo "Names found in the text are added by themselves; --not-about drops a wrong one."
    echo "holders: who knows it. Default: the player and the NPCs present."
    echo "--also adds to it; --holders replaces it (player, npc:<name>, street, public);"
    echo "--secret: nobody. Present = the party and the scene list (gm-scene.sh)."
    echo "A wrong or partial version: --truth wrong|partial [--version-of <fact id>]."
    echo ""
    echo "Example: gm-note.sh session_events \"Wren paid off Dekker\" --about location:Lanternside"
}

if [ "$#" -lt 1 ]; then
    usage
    exit 1
fi

require_active_campaign

# "gm-note.sh add <category> <fact>" is the same as "gm-note.sh <category> <fact>"
# (an easy guess; without this, "add" became the category and the fact an extra argument).
if [ "$1" = "add" ]; then
    shift
fi

case "$1" in
    get)
        # Gone: it printed facts.json raw, without the [SECRET] and [HIDDEN FROM
        # PLAYER] marks. Refused here, or "get" would be recorded as a category.
        echo "[ERROR] gm-note.sh get is gone. Look facts up with:" >&2
        echo "  gm-note.sh recent [N]  |  find --category <c> / --about <id> / --held-by <id> / --text \"words\"  |  show <fact id>" >&2
        exit 1
        ;;
    tell|about|truth|categories|show|find|recent|beat|witness)
        $PYTHON_CMD "$LIB_DIR/note_manager.py" "$@"
        ;;
    *)
        if [ "$#" -lt 2 ]; then
            usage
            exit 1
        fi
        $PYTHON_CMD "$LIB_DIR/note_manager.py" add "$@"
        ;;
esac
