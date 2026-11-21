#!/bin/bash
# gm-time.sh - In-game time (wrapper for time_manager.py)
#
#   gm-time.sh                          Show the current time
#   gm-time.sh advance <duration>       Let time pass: 10m, 4h, 2d, 1w, "1h 30m"; it stops
#                                       at the first moment with something to play now
#       --through "<name>"              ...but not for this rule, "<rule>:<outcome>",
#                                       consequence id or clock (repeatable)
#       --through                       never stops: a montage, with the timeline
#       --rest                          the character lies still (asleep, a hospital
#                                       bed): wounds heal twice as fast
#   gm-time.sh set "YYYY-MM-DD HH:MM"   Set the time outright (campaign start, or a correction)
#
# `advance` walks from one moment at which something changes to the next (clocks,
# the world's rules, consequences), each printed with its time; `set` is one jump.

source "$(dirname "$0")/common.sh"

usage() {
    echo "Usage: gm-time.sh                          Show the current time"
    echo "       gm-time.sh advance <duration>       e.g. 10m, 4h, 2d, 1w, \"1h 30m\"; stops at the"
    echo "                                           first moment with something to play now"
    echo "           --through \"<name>\"              not for this rule, \"<rule>:<outcome>\","
    echo "                                           consequence id or clock (repeatable)"
    echo "           --through                       never stops (a montage)"
    echo "           --rest                          asleep or in a hospital bed: wounds heal faster"
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
        # The consequences are checked at each moment as time passes (time_manager.py).
        $PYTHON_CMD "$LIB_DIR/time_manager.py" "$@" || exit $?
        ;;
    *)
        usage
        exit 1
        ;;
esac
