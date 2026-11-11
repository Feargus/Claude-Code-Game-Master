#!/bin/bash
# gm-combat.sh - Persisted fight state: each enemy's wounds and notes
#
#   gm-combat.sh start
#   gm-combat.sh add-enemy "street thug 1" --as "street thug"   # wounds from its sheet
#   gm-combat.sh add-enemy "Rook" --as Rook                      # an NPC, the same way
#   gm-combat.sh add-enemy "something odd" 2                     # or the wounds by hand
#   gm-combat.sh wound "street thug 1" 1 --note "right arm disabled"
#   gm-combat.sh condition "street thug 1" add prone
#   gm-combat.sh header        # show the fight
#   gm-combat.sh end           # clear state; each enemy taken out gives XP (wounds² × 10)
#
# Add --json to any command for a structured envelope.

source "$(dirname "$0")/common.sh"

require_active_campaign

$PYTHON_CMD "$LIB_DIR/combat_manager.py" "$@"
