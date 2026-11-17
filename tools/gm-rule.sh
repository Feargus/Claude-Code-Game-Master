#!/bin/bash
# gm-rule.sh - The world's own rules (wrapper for world_rules.py)
#
#   gm-rule.sh list                                  every rule, and where it stands
#   gm-rule.sh show "<rule>" [holder]                one rule in full
#   gm-rule.sh change "<rule>" [holder] +N|-N        a counter goes up or down
#   gm-rule.sh set "<rule>" [holder] N               a counter is set to a value
#   gm-rule.sh reveal|hide "<rule>" [holder]         one holder's value becomes known or hidden
#   gm-rule.sh define <<'EOF' [...] EOF              add or replace rules (a JSON list)
#   gm-rule.sh plain <<'EOF' lines EOF               the plain rule lines (no mechanic)
#   gm-rule.sh remove "<rule>"                       remove a rule and its values
#
# The holder is the player, an NPC, a place, faction:<id> or world; it can be left
# out when the rule is held only by the player or only by the world.

source "$(dirname "$0")/common.sh"

if [ "$#" -lt 1 ] || [ "$1" = "help" ] || [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    sed -n '3,15p' "$0" | sed 's/^# \{0,1\}//'
    exit 0
fi

require_active_campaign

$PYTHON_CMD "$LIB_DIR/world_rules.py" "$@"
