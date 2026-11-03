#!/bin/bash
# gm-time.sh - In-game time (wrapper for time_manager.py)
#
#   gm-time.sh                          Show the current time
#   gm-time.sh advance <duration>       Let time pass: 10m, 4h, 2d, 1w, "1h 30m"
#   gm-time.sh set "YYYY-MM-DD HH:MM"   Set the time outright (campaign start, or a correction)
#
# Both `advance` and `set` recompute the time clocks from the new time.

source "$(dirname "$0")/common.sh"

usage() {
    echo "Usage: gm-time.sh                          Show the current time"
    echo "       gm-time.sh advance <duration>       e.g. 10m, 4h, 2d, 1w, \"1h 30m\""
    echo "       gm-time.sh set \"YYYY-MM-DD HH:MM\"   Campaign start, or a correction"
}

require_active_campaign

case "${1:-show}" in
    show)
        $PYTHON_CMD "$LIB_DIR/time_manager.py" show
        ;;
    advance|set)
        if [ "$#" -lt 2 ]; then
            usage
            exit 1
        fi
        $PYTHON_CMD "$LIB_DIR/time_manager.py" "$@" || exit $?
        # Reactivity: time passing can fire on_time consequences (e.g. nightfall, deadlines).
        echo ""
        bash "$TOOLS_DIR/gm-consequence.sh" tick
        ;;
    *)
        usage
        exit 1
        ;;
esac
