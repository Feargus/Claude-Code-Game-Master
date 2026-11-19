#!/bin/bash
# gm-dice.sh - Dice for the moment (thin wrapper for dice.py)
#
#   gm-dice.sh "<dice>"     Roll and print the sum, nothing else: 1d20, 1d20+5, 2d6, d6,
#                           2d6+1d4-1
#
# For a one-off chance in the story (does the frayed rope hold: it snaps on 1-2 of a
# d6, the odds set before the roll; how long a storm lasts). A chance the world has
# as a rule, read the same way every time, rolls with gm-rule.sh roll instead.
# An action someone takes is a skill contest (gm-skill-contest.sh), never this.

source "$(dirname "$0")/common.sh"

if [ "$#" -ne 1 ] || [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    echo "Usage: gm-dice.sh \"<dice>\"   e.g. 1d20, 1d20+5, 2d6, d6, 2d6+1d4-1"
    echo "  One-off chance in the story. A world rule's roll: gm-rule.sh roll. An action: gm-skill-contest.sh."
    [ "$#" -eq 1 ] && exit 0
    exit 1
fi
$PYTHON_CMD "$LIB_DIR/dice.py" "$1"
