#!/bin/bash
# gm-condition.sh - The player character's conditions (thin wrapper for player_manager.py)
# Interface: gm-condition.sh add|remove <condition> / gm-condition.sh check
# No name: a campaign has one player character.

source "$(dirname "$0")/common.sh"

usage() {
    echo "Usage: gm-condition.sh add <condition>     - add a condition to the player character"
    echo "       gm-condition.sh remove <condition>  - remove one"
    echo "       gm-condition.sh check               - show the current conditions"
    echo ""
    echo "Example: gm-condition.sh add grappled"
}

ACTION="$1"
case "$ACTION" in
    add|remove)
        if [ "$#" -ne 2 ]; then
            usage
            exit 1
        fi
        require_active_campaign
        $PYTHON_CMD "$LIB_DIR/player_manager.py" condition "$ACTION" "$2"
        ;;
    check)
        if [ "$#" -ne 1 ]; then
            usage
            exit 1
        fi
        require_active_campaign
        $PYTHON_CMD "$LIB_DIR/player_manager.py" condition list
        ;;
    *)
        usage
        exit 1
        ;;
esac

exit $?
