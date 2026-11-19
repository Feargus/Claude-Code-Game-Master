#!/bin/bash
# gm-rule.sh - The world's own rules (wrapper for world_rules.py)
#
#   gm-rule.sh list                                  every rule, and where it stands
#   gm-rule.sh show "<rule>" [holder]                one rule in full
#   gm-rule.sh change "<rule>" [holder] +N|-N        a counter goes up or down
#   gm-rule.sh set "<rule>" [holder] N               a counter is set to a value
#   gm-rule.sh roll "<rule>" [holder] [--with "<amount>"]...   a roll, read from its results
#   gm-rule.sh move "<rule>" [holder] <state>        a states rule moves (set: any state)
#   gm-rule.sh draw "<bag>" [holder] [N]             draw tokens from a bag
#   gm-rule.sh put|take "<bag>" [holder] <kind> N    add tokens, or take them out
#   gm-rule.sh refill "<bag>" [holder]               back to its first tokens
#   gm-rule.sh split "<budget>" [holder] <part>=N ...   split a budget (all of it)
#   gm-rule.sh refill "<budget>" [holder]            a spent budget is full again
#   gm-rule.sh reveal|hide "<rule>" [holder]         one holder's value becomes known or hidden
#   gm-rule.sh break "<rule>" [holder]               a streak ends: back to its start
#   gm-rule.sh mark "<rule>" [holder] "<mark>"       the lasting mark an overflow left
#   gm-rule.sh rate "<rule>" [holder] [--by N] [--every 90d] [--toward N | --shift N]
#                                                    one holder's own rate, and its own point
#   gm-rule.sh define <<'EOF' [...] EOF              add or replace rules (a JSON list)
#   gm-rule.sh plain <<'EOF' lines EOF               the plain rule lines (no mechanic)
#   gm-rule.sh remove "<rule>"                       remove a rule and its values
#
# The holder is the player, an NPC, a place, faction:<id> or world; it can be left
# out when the rule is held only by the player or only by the world.

source "$(dirname "$0")/common.sh"

if [ "$#" -lt 1 ] || [ "$1" = "help" ] || [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    sed -n '3,25p' "$0" | sed 's/^# \{0,1\}//'
    exit 0
fi

require_active_campaign

$PYTHON_CMD "$LIB_DIR/world_rules.py" "$@"
