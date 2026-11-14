#!/bin/bash
# gm-mob.sh - Mobs: interchangeable enemies with stats (wrapper for stat_block.py)
#
#   gm-mob.sh list                       this campaign's mobs, and the repo's examples (the scale)
#   gm-mob.sh show "<mob>"
#   gm-mob.sh add "<mob>" --note "..." [--attr STR=14] [--attr default=10]... [--skill Brawling=3]... [--wounds N]
#                                        stats and wounds may come later, before it is rolled or fought
#   gm-mob.sh stats "<mob>" [--attr ...] [--skill ...] [--remove-skill X] [--wounds N] [--note "..."]
#
# Everything is checked before it is saved; never edit mobs.json by hand.

source "$(dirname "$0")/common.sh"

require_active_campaign

$PYTHON_CMD "$LIB_DIR/stat_block.py" "$@"
