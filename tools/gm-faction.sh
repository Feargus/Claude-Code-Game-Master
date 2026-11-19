#!/bin/bash
# gm-faction.sh - Factions: a group with a goal, impulses and values (wrapper for factions.py)
#
#   gm-faction.sh create "<name>" --description "..." [--id <short id>] [--kind "..."]
#                  [--impulse "..."]... [--value "..."]... [--alias "..."]... [--tag <tag>]...
#                  [--leader <npc>] [--successor <npc>] [--another]
#                                      a new faction; its id (faction:<id>) never changes
#   gm-faction.sh set <faction> <field> [<value>...]
#                                      replace a field: name, kind, description, leader,
#                                      successor, or a whole list: impulses, values, tags
#                                      (each its own quoted value; none clears it)
#   gm-faction.sh alias <faction> <alias>... [--remove <alias>]
#   gm-faction.sh asset <faction> "<name>" "<what it is>" [--remove]
#   gm-faction.sh tie <faction> <other> ["<how it sees the other, a line>"]
#                                      a history between two factions (no text removes it);
#                                      the number is the Relation (gm-rule.sh)
#   gm-faction.sh join <faction> <npc> [--secret | --open]
#                                      a member: knows what the faction knows (their on_learn
#                                      consequences fire); --secret: only its members know it;
#                                      a member already: --secret / --open change only that
#   gm-faction.sh leave <faction> <npc>  no longer knows what only the faction knew
#   gm-faction.sh show <faction>       the faction, its world-rule values, the facts it knows
#   gm-faction.sh list                 every faction, one line each
#   gm-faction.sh from-bible           an older campaign: copy the world bible's factions in
#   gm-faction.sh turn [--only <faction>] <<'EOF'
#                                      a faction turn (/gm world): one action per faction
#                                      (--only: that faction alone takes its turn),
#     [{"faction": "<id>", "action": "<action>", "power": "Military|Economic|Political|Covert",
#       "rival": "<id>", "at": "<place>", "asset": "<name>", "who": "<npc>", "plot": "<plot>",
#       "note": "<what they do, a few words>"}, ...]
#     EOF                              simple: build, reinforce, push, prepare
#                                      complex (facts, cost 2, 3 failed): strike, seize, take,
#                                      spy, expose, deal, enact (lib/faction_turns.py)
#
# Its goal is a plot it owns, its secrets are facts it holds (gm-note.sh --holders
# faction:<id>), its own numbers are world rules held by factions (gm-rule.sh).

source "$(dirname "$0")/common.sh"

if [ "$#" -lt 1 ] || [ "$1" = "help" ] || [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    sed -n '3,36p' "$0" | sed 's/^# \{0,1\}//'
    exit 0
fi

require_active_campaign

$PYTHON_CMD "$LIB_DIR/factions.py" "$@"
