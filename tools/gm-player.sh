#!/bin/bash
# Player Character management
# Thin CLI wrapper - logic in lib/player_manager.py

# Source common utilities
source "$(dirname "$0")/common.sh"

require_active_campaign

ACTION=$1
shift

case "$ACTION" in
    "show")
        # Optional [name] and optional --json (full record). Pass all through.
        $PYTHON_CMD "$LIB_DIR/player_manager.py" show "$@"
        ;;

    "list")
        $PYTHON_CMD "$LIB_DIR/player_manager.py" list
        ;;

    "create")
        if [ -z "$1" ]; then
            echo "Usage: gm-player.sh create '<character json>' [--canon \"<NPC>\"] [--replace]"
            echo ""
            echo "Saves the character from a finished interview; anything left out gets a default."
            echo "  --canon NPC   the character is this NPC from the campaign"
            echo "  --replace     hand the story to a new PC (archives the current one to fallen/)"
            exit 1
        fi
        $PYTHON_CMD "$LIB_DIR/new_character.py" "$@"
        ;;

    "set")
        if [ -z "$1" ]; then
            echo "Usage: gm-player.sh set <character_name>"
            exit 1
        fi
        $PYTHON_CMD "$LIB_DIR/player_manager.py" set "$1"
        ;;

    "xp")
        if [ -z "$1" ] || [ -z "$2" ]; then
            echo "Usage: gm-player.sh xp <character_name> <+amount>"
            exit 1
        fi
        $PYTHON_CMD "$LIB_DIR/player_manager.py" xp "$1" "$2"
        ;;

    "award")
        # Discretionary spectacle XP (kit-aware, level-scaled; co-awards followers).
        # Name optional (defaults to active PC). Requires --tier; --reason optional.
        $PYTHON_CMD "$LIB_DIR/player_manager.py" award "$@"
        ;;

    "level-check")
        if [ -z "$1" ]; then
            echo "Usage: gm-player.sh level-check <character_name>"
            exit 1
        fi
        $PYTHON_CMD "$LIB_DIR/player_manager.py" level-check "$1"
        ;;

    "vital")
        if [ -z "$1" ]; then
            echo "Usage: gm-player.sh vital <vital_name> [<+/-amount> | set <value>]"
            echo "Example: gm-player.sh vital vigor -2      (spend 2 vigor)"
            echo "Example: gm-player.sh vital corruption +1 (gain 1 corruption)"
            echo "Example: gm-player.sh vital vigor set 5   (set vigor to 5)"
            echo "Example: gm-player.sh vital corruption    (show current)"
            echo "Vitals are whatever the World Kit declares (ruleset.json stat_schema.vitals)."
            exit 1
        fi
        $PYTHON_CMD "$LIB_DIR/player_manager.py" vital "$@"
        ;;

    "get")
        if [ -z "$1" ]; then
            echo "Usage: gm-player.sh get <character_name>"
            exit 1
        fi
        NAME="$1"; shift
        $PYTHON_CMD "$LIB_DIR/player_manager.py" get "$NAME" "$@"
        ;;

    "kill")
        if [ -z "$1" ]; then
            echo "Usage: gm-player.sh kill <character_name> [--cause \"<how>\"]"
            echo "Example: gm-player.sh kill Tandy --cause \"crushed by the Iron Tangle\""
            exit 1
        fi
        NAME="$1"; shift
        $PYTHON_CMD "$LIB_DIR/player_manager.py" kill "$NAME" "$@"
        ;;

    "become")
        if [ -z "$1" ]; then
            echo "Usage: gm-player.sh become <party_member_name>"
            echo "Take over a party member as the active PC (Death Protocol hand-off)."
            echo "Archives the fallen PC to the campaign's fallen/ dir."
            exit 1
        fi
        NAME="$1"; shift
        $PYTHON_CMD "$LIB_DIR/player_manager.py" become "$NAME" "$@"
        ;;

    "credits")
        if [ -z "$1" ]; then
            echo "Usage: gm-player.sh credits <character_name> [+/-amount]"
            echo "Example: gm-player.sh credits theron +50  (gain 50 credits)"
            echo "Example: gm-player.sh credits theron -10  (spend 10 credits)"
            echo "Example: gm-player.sh credits theron      (show current credits)"
            exit 1
        fi
        if [ -z "$2" ]; then
            $PYTHON_CMD "$LIB_DIR/player_manager.py" credits "$1"
        else
            $PYTHON_CMD "$LIB_DIR/player_manager.py" credits "$1" "$2"
        fi
        ;;

    "inventory")
        # All positionals are optional: defaults to the active PC and `list`.
        # Forms: `inventory` · `inventory list` · `inventory <name> <action> [item]`.
        $PYTHON_CMD "$LIB_DIR/player_manager.py" inventory "$@"
        ;;

    "loot")
        if [ -z "$1" ]; then
            echo "Usage: gm-player.sh loot <character_name> --credits <amount> --items \"Item1\" \"Item2\" ..."
            echo ""
            echo "Examples:"
            echo "  gm-player.sh loot Fearghas --credits 47 --items \"Data chip\" \"Stim pak\""
            echo "  gm-player.sh loot Tandy --items \"Scroll of Fireball\""
            echo "  gm-player.sh loot Fearghas --credits 100"
            exit 1
        fi
        $PYTHON_CMD "$LIB_DIR/player_manager.py" loot "$@"
        ;;

    "raise")
        if [ -z "$1" ] || [ -z "$2" ]; then
            echo "Usage: gm-player.sh raise attribute <ATTR>     (one die size up, e.g. DFT)"
            echo "       gm-player.sh raise skill \"<skill>\"     (+1; a new skill starts at 1)"
            exit 1
        fi
        $PYTHON_CMD "$LIB_DIR/player_manager.py" raise "$1" "$2"
        ;;

    "perk")
        if [ -z "$1" ] || [ -z "$2" ]; then
            echo "Usage: gm-player.sh perk \"<name>\" \"<what it does>\""
            echo "Example: gm-player.sh perk \"Night eyes\" \"+2 Awareness in the dark, -2 in bright light\""
            exit 1
        fi
        $PYTHON_CMD "$LIB_DIR/player_manager.py" perk "$1" "$2"
        ;;

    "condition")
        if [ -z "$1" ] || [ -z "$2" ]; then
            echo "Usage: gm-player.sh condition <character_name> <action> [condition]"
            echo ""
            echo "Actions:"
            echo "  add <condition>    - Add condition to character"
            echo "  remove <condition> - Remove condition from character"
            echo "  list               - Show current conditions"
            echo ""
            echo "Example: gm-player.sh condition Tandy add poisoned"
            echo "Example: gm-player.sh condition Tandy remove poisoned"
            echo "Example: gm-player.sh condition Tandy list"
            exit 1
        fi
        if [ "$2" = "list" ]; then
            $PYTHON_CMD "$LIB_DIR/player_manager.py" condition "$1" "$2"
        else
            if [ -z "$3" ]; then
                echo "Error: Condition name required for $2"
                exit 1
            fi
            $PYTHON_CMD "$LIB_DIR/player_manager.py" condition "$1" "$2" "$3"
        fi
        ;;

    "appearance")
        $PYTHON_CMD "$LIB_DIR/player_manager.py" appearance "$@"
        ;;

    "set-appearance")
        $PYTHON_CMD "$LIB_DIR/player_manager.py" set-appearance "$@"
        ;;

    *)
        echo "Player Character Manager"
        echo "Usage: gm-player.sh <action> [args]"
        echo ""
        echo "Actions:"
        echo "  show [name] [--json]         - Show summary (or full record with --json)"
        echo "  get <name>                   - Get full character JSON"
        echo "  list                         - List all player IDs"
        echo "  create '<json>' [--canon N] [--replace] - Save a new character from the interview"
        echo "  set <name>                   - Set character as current active PC"
        echo "  xp <name> +<amount>          - Award XP to character"
        echo "  award [name] --tier T        - Spectacle XP for a clever/effective/unique/punishing beat (T=minor|major|legendary; --reason \"...\"; co-awards followers)"
        echo "  vital <vital> <+/-N|set N>   - Read/change a kit vital (vigor, corruption, ...)"
        echo "  kill <name> [--cause ...]    - Mark PC dead (then run Death Protocol)"
        echo "  become <party_member>        - Take over a party member as the active PC"
        echo "  credits <name> [+/-amount]   - Modify or show character credits"
        echo "  inventory [name] [action]    - Manage inventory (add/remove/list; defaults to active PC + list)"
        echo "  condition <name> <action>    - Manage conditions (add/remove/list)"
        echo "  raise attribute|skill <x>    - Level-up: +1 to an attribute (die size) or a skill"
        echo "  perk <name> <what it does>   - Add or rewrite a perk"
        echo "  loot <name> --credits X --items - Batch add items + credits at once"
        echo "  level-check <name>           - Check XP and level status"
        echo ""
        echo "Note: Character is stored in the active campaign's character.json"
        if [ -n "$ACTION" ]; then
            echo "Error: unknown action '$ACTION'" >&2
            exit 1
        fi
        ;;
esac

# Propagate Python exit code
exit $?
