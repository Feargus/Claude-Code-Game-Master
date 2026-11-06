#!/bin/bash
# gm-note.sh - Record world facts (wrapper for note_manager.py)

source "$(dirname "$0")/common.sh"

usage() {
    echo "Usage: gm-note.sh <category> <fact> [--about <id>]... [--not-about <id>]..."
    echo "       gm-note.sh about <fact id> [--add <id>]... [--remove <id>]..."
    echo "       gm-note.sh categories"
    echo ""
    echo "Categories: session_events, plot_local, plot_regional, plot_world,"
    echo "            player_choices, npc_relations, lore, rules"
    echo ""
    echo "about: who or what the fact concerns: player, npc:<name>, location:<name>."
    echo "Names found in the text are added by themselves; --not-about drops a wrong one."
    echo ""
    echo "Example: gm-note.sh session_events \"Wren paid off Dekker\" --about location:Lanternside"
}

if [ "$#" -lt 1 ]; then
    usage
    exit 1
fi

require_active_campaign

case "$1" in
    categories)
        echo "Fact Categories:"
        $PYTHON_CMD "$LIB_DIR/note_manager.py" categories
        ;;
    about)
        shift
        $PYTHON_CMD "$LIB_DIR/note_manager.py" about "$@"
        ;;
    *)
        if [ "$#" -lt 2 ]; then
            usage
            exit 1
        fi
        $PYTHON_CMD "$LIB_DIR/note_manager.py" add "$@"
        ;;
esac
