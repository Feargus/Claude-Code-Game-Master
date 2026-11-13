#!/bin/bash
# NPC sheets (sheet.py format). Thin wrapper: logic in lib/npc_manager.py.

source "$(dirname "$0")/common.sh"

usage() {
    echo "Usage: gm-npc.sh <action> [name] [args]"
    echo ""
    echo "  create <name> \"<role>\" [\"<attitude>\"] --location <place>... | --nowhere [--alias <short name>]..."
    echo "         [field flags]           Create an NPC. The attitude is their attitude towards the player,"
    echo "                                 as one or more adjectives, comma separated (\"wary\", \"fond,"
    echo "                                 exasperated\"), never a sentence; leave it out if they have none."
    echo "                                 It becomes a fact they hold. Only name, role and place are needed;"
    echo "                                 add the rest when play needs it."
    echo "  set <name> [field flags]       Fill in or change fields (\"\" clears one)"
    echo "       field flags: --race --role --background --affiliation"
    echo "                    --physique --style --presence                  (look)"
    echo "                    --big-five \"O1 C-2 E3 A-1 N2\" --demeanor --voice --tells"
    echo "                    --want --need --values --fears                 (personality)"
    echo "                    --goal                                         (what they're after now)"
    echo "  show <name>                    The whole sheet, and what they know and feel about the player"
    echo "  stats <name> [--attr STR=12]... [--skill Handguns=4]... [--remove-skill X] [--wounds N]"
    echo "  alias <name> <alias>... [--remove <alias>]"
    echo "  tag-location / untag-location <name> <place>...   Usual places (known locations)"
    echo "  item <name> add gear|inventory \"<item>\" [--concealed]  /  item <name> remove \"<item>\""
    echo "  kill <name> [--cause \"<how>\"]  Dead; fires its on_death consequences"
    echo "  promote / demote <name>        Into or out of the party (present wherever the player is)"
    echo "  party                          The party members"
    echo "  list [--location <place>]"
    echo ""
    echo "What an NPC knows, feels, remembers or hides: facts (gm-note.sh ... --holders npc:<name>)."
}

ACTION="$1"
[ -z "$ACTION" ] && { usage; exit 1; }
shift

case "$ACTION" in
    show|status)
        NAME="$1"
        STATUS_OUTPUT=$($PYTHON_CMD "$LIB_DIR/npc_manager.py" show "$@")
        STATUS_CODE=$?
        echo "$STATUS_OUTPUT"
        [ $STATUS_CODE -ne 0 ] && exit $STATUS_CODE
        # A campaign from a book: what the book says about them.
        CAMPAIGN_DIR=$(bash "$TOOLS_DIR/gm-campaign.sh" path 2>/dev/null)
        if [ -n "$NAME" ] && [ -d "$CAMPAIGN_DIR/vectors" ]; then
            echo ""
            echo "Source Material Context"
            echo "======================="
            $PYTHON_CMD "$LIB_DIR/entity_enhancer.py" search "$NAME personality dialogue background" -n 4 --excerpt-chars 250
        fi
        ;;
    create|set|stats|alias|tag-location|untag-location|item|kill|promote|demote|party|list)
        $PYTHON_CMD "$LIB_DIR/npc_manager.py" "$ACTION" "$@"
        ;;
    *)
        usage
        exit 1
        ;;
esac
