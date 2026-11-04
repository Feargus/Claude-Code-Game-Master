#!/bin/bash
# gm-combat.sh - Persisted fight state: each enemy's wounds and notes
#
#   gm-combat.sh start
#   gm-combat.sh add-enemy "street thug 1" 2              # wounds that take it out
#   gm-combat.sh wound "street thug 1" 1 --note "right arm disabled"
#   gm-combat.sh condition "street thug 1" add prone
#   gm-combat.sh header        # show the fight
#   gm-combat.sh end           # clear state (award XP/loot via gm-player afterwards)
#
# Add --json to any command for a structured envelope.

source "$(dirname "$0")/common.sh"

require_active_campaign

$PYTHON_CMD "$LIB_DIR/combat_manager.py" "$@"
