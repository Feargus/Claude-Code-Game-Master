#!/bin/bash
# gm-scene.sh - Who is in the current scene (wrapper for scene_manager.py)
#
#   gm-scene.sh                       Show who is here (and who is usually found here)
#   gm-scene.sh enter <npc>...        NPCs join the scene; on_npc consequences are checked
#   gm-scene.sh leave <npc>...        NPCs leave the scene
#
# Party members are always present. Every move resets the scene to the party.

source "$(dirname "$0")/common.sh"

require_active_campaign

case "${1:-show}" in
    show)
        $PYTHON_CMD "$LIB_DIR/scene_manager.py" show
        ;;
    enter)
        $PYTHON_CMD "$LIB_DIR/scene_manager.py" "$@" || exit $?
        # Reactivity: an NPC walking in can fire on_npc consequences.
        echo ""
        bash "$TOOLS_DIR/gm-consequence.sh" tick
        ;;
    leave)
        $PYTHON_CMD "$LIB_DIR/scene_manager.py" "$@"
        ;;
    *)
        echo "Usage: gm-scene.sh [show] | enter <npc>... | leave <npc>..."
        exit 1
        ;;
esac
