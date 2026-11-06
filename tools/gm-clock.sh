#!/bin/bash
# gm-clock.sh - Threat clocks (thin wrapper for threat_clocks.py)
#
#   gm-clock.sh list                          Show all clocks
#   gm-clock.sh add "Name" 6 [--on time|event] [--consequence "..."] [--linked-plot "..."]
#                    [--due-in 3d | --due "YYYY-MM-DD HH:MM"]
#                                             New clock with N segments; the
#                                             consequence fires into the world when it fills.
#                                             A time clock fills as game time passes and is
#                                             full when due (default: one day per segment)
#   gm-clock.sh advance "Name" [--ticks 2]    Advance an event clock by hand
#                                             (a time clock fills only as time passes)
#   gm-clock.sh beats                         Filled clocks = dramatic beats due
#   gm-clock.sh remove "Name"                 Remove a clock
#
# All commands accept --json.

source "$(dirname "$0")/common.sh"

require_active_campaign

$PYTHON_CMD "$LIB_DIR/threat_clocks.py" "$@"
