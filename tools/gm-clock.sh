#!/bin/bash
# gm-clock.sh - Threat clocks (thin wrapper for threat_clocks.py)
#
#   gm-clock.sh list                          Show all clocks
#   gm-clock.sh add "Name" 6 [--text "what it is about"] [--on time|event]
#                    [--consequence "..."] [--linked-plot "..."]
#                    [--due-in 3d | --due "YYYY-MM-DD HH:MM"]
#                                             New clock with N segments. The name is a short
#                                             key (one to three words: "Tracker"), which
#                                             triggers and commands use; it never changes. The
#                                             consequence fires into the world when it fills.
#                                             A time clock fills as game time passes and is
#                                             full when due (default: one day per segment)
#   gm-clock.sh advance "Name" [--ticks 2]    Advance an event clock by hand
#                                             (a time clock fills only as time passes)
#   gm-clock.sh due "Name" --earlier 1d | --later 6h | --due-in 12h | --due "YYYY-MM-DD HH:MM"
#                                             Move a time clock's due time; it is
#                                             recomputed at once (may fill and fire)
#   gm-clock.sh text "Name" "new text"        Reword what a clock is about (its name stays)
#   gm-clock.sh beats                         Filled clocks = dramatic beats due
#   gm-clock.sh remove "Name"                 Remove a clock
#
# All commands accept --json.

source "$(dirname "$0")/common.sh"

if [ "$#" -lt 1 ] || [ "$1" = "help" ] || [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    sed -n '3,22p' "$0" | sed 's/^# \{0,1\}//'
    exit 0
fi

require_active_campaign

$PYTHON_CMD "$LIB_DIR/threat_clocks.py" "$@"
