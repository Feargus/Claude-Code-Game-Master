#!/bin/bash
# The player character's sheet (sheet.py format). Thin wrapper: logic in lib/player_manager.py.

source "$(dirname "$0")/common.sh"

require_active_campaign

ACTION=$1
shift

case "$ACTION" in
    "create")
        if [ -z "$1" ]; then
            echo "Usage: gm-player.sh create '<character json>' [--canon \"<NPC>\"] [--replace]"
            echo ""
            echo "Saves the character from a finished interview (/create-character); anything left out gets a default."
            echo "  --canon NPC   the character is this NPC from the campaign"
            echo "  --replace     hand the story to a new PC (archives the current one to fallen/)"
            exit 1
        fi
        $PYTHON_CMD "$LIB_DIR/new_character.py" "$@"
        ;;

    "show"|"get"|"set"|"xp"|"award"|"grow"|"level-check"|"raise"|"perk"|"vital"|"kill"|"credits"|"item"|"loot"|"condition")
        $PYTHON_CMD "$LIB_DIR/player_manager.py" "$ACTION" "$@"
        ;;

    *)
        echo "Player Character Manager"
        echo "Usage: gm-player.sh <action> [args]"
        echo ""
        echo "  create '<json>' [--canon N] [--replace] - save a new character from the interview"
        echo "  show [--json]                - the whole sheet (JSON with --json; get is the same)"
        echo "  set --style \"...\" ...        - text fields: identity, look, personality"
        echo "                                 (--race --role --background --affiliation --physique --style"
        echo "                                  --presence --big-five --demeanor --voice --tells --want --need"
        echo "                                  --values --fears --goal; \"\" clears one)"
        echo "  item add gear|inventory \"<item>\" [--concealed] [--note \"...\"]"
        echo "  item remove|move \"<item>\" [--to gear|inventory]   item list"
        echo "  loot <name> --credits X --items \"A\" \"B\"  - into the inventory, plus credits"
        echo "  credits <name> [+/-amount]   - show or change credits"
        echo "  condition <name> add|remove|list [<condition>]"
        echo "  vital <counter> [+/-N | set N] - the campaign's own counters (Drift, ...)"
        echo "  award --size small|medium|large --reason \"...\" - XP for an achievement"
        echo "  grow --attribute A --skill S --skill T --perk \"Name\" \"Effect\" - growth that is due (gm-growth)"
        echo "  level-check                  - XP, level, growth due"
        echo "  kill <name> [--cause ...]    - the PC dies (then the Death Protocol)"
        echo "  xp <name> +N [--reason ...]  - correction: XP by hand (logged)"
        echo "  raise attribute|skill <x>    - correction: +1"
        echo "  perk \"<name>\" \"<effect>\"     - correction: add or rewrite a perk"
        echo ""
        echo "Wounds, armor and cyberware: gm-body.sh."
        [ -z "$ACTION" ] && exit 1
        exit 1
        ;;
esac
