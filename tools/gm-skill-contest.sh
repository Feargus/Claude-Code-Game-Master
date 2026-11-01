#!/bin/bash
# gm-skill-contest.sh - Roll a skill contest (wrapper for skill_contest.py)

source "$(dirname "$0")/common.sh"

if [ "$#" -lt 1 ]; then
    echo "Usage: gm-skill-contest.sh --active NAME SKILL ATTR ATTR ATTR | --active-dc DC LABEL"
    echo "                           --reactive NAME SKILL ATTR ATTR ATTR | --reactive-dc DC LABEL"
    echo "                           [--active-adv ATTR...] [--active-dis ATTR...]"
    echo "                           [--reactive-adv ATTR...] [--reactive-dis ATTR...]"
    echo "                           [--mod VALUE LABEL]..."
    echo ""
    echo "Prints the quality. >= 0 means the active side succeeds."
    echo ""
    echo "Example: gm-skill-contest.sh --active Fearghas \"Long guns\" DFT AGI ITU \\"
    echo "           --reactive rat Evasion AGI ITU NRV --reactive-dis NRV --mod -2 \"darkness\""
    exit 1
fi

require_active_campaign

$PYTHON_CMD "$LIB_DIR/skill_contest.py" "$@"
