#!/bin/bash
# gm-plot.sh - Plots: someone's goal with progress, or the problem the story turns on
# (wrapper for plot_manager.py)
#
#   gm-plot.sh add "<key>" --description "..." [--owner <player, npc or faction>] [--goal "..."] [--kind K]
#                  [--involves <npc, place or faction>]... [--stands "..."] [--follows "<key>"] [--another]
#                                      a new plot; the key is a short name that never changes
#   gm-plot.sh stands "<key>" "<where it stands now>"
#   gm-plot.sh involve "<key>" <npc, place or faction>... [--remove <one>]
#   gm-plot.sh description "<key>" "<what it is about>"
#   gm-plot.sh complete|fail "<key>" "<what came of it>" [--next "<key>"]
#                                      --next: the plot that replaces it (add it first)
#   gm-plot.sh show "<key>"            the plot with its clocks, consequences and facts
#   gm-plot.sh list [--status open|completed|failed]   open plots, most pressing first
#
# Kinds: main, antagonist, mystery, conspiracy, background (lib/schemas.py, PLOT_KINDS).
# Facts, clocks, consequences and glossary entries join a plot with --plot "<key>".

source "$(dirname "$0")/common.sh"

if [ "$#" -lt 1 ] || [ "$1" = "help" ] || [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    sed -n '3,19p' "$0" | sed 's/^# \{0,1\}//'
    exit 0
fi

require_active_campaign

$PYTHON_CMD "$LIB_DIR/plot_manager.py" "$@"
