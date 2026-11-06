#!/bin/bash
# gm-consequence.sh - Consequence tracking (thin wrapper for consequence_manager.py)

source "$(dirname "$0")/common.sh"

if [ "$#" -lt 1 ]; then
    echo "Usage: gm-consequence.sh <action> [args]"
    echo ""
    echo "Actions:"
    echo "  add <description> <trigger>    - Add new consequence"
    echo "  tick                           - Fire consequences matching the current scene (auto on move/time)"
    echo "  check                          - Check pending consequences"
    echo "  fire <id> [--by <fact id>] [--reason \"...\"]"
    echo "                                 - Fire a consequence by hand (its condition happened)"
    echo "  resolve <id>                   - Resolve a consequence (once it has played out)"
    echo "  (an id may be shortened to a unique prefix, e.g. the 4 characters the brief shows)"
    echo "  list-resolved                  - List resolved consequences"
    echo ""
    echo "Examples:"
    echo "  gm-consequence.sh add \"Guards searching for party\" \"2 days\""
    echo "  gm-consequence.sh add \"The tracker arrives\" \"tracker clock full\" --trigger-type on_clock --match \"Tracker\""
    echo "  gm-consequence.sh add \"Footprints at the door\" \"halfway\" --trigger-type on_clock --match \"Tracker:2\""
    echo "  gm-consequence.sh check"
    echo "  gm-consequence.sh resolve abc123"
    exit 1
fi

require_active_campaign

ACTION="$1"
shift

case "$ACTION" in
    add)
        if [ "$#" -lt 2 ]; then
            echo "Usage: gm-consequence.sh add <description> <trigger> [--trigger-type T --match M --expiry E]"
            echo "Triggers: immediate, next visit, 2 days, next session, etc."
            echo "Structured: --trigger-type on_location|on_npc|on_time|on_event --match <value> [--expiry <date|cond>]"
            echo "Several triggers: repeat --trigger-type/--match pairs, in order; any one fires it."
            exit 1
        fi
        DESC="$1"; TRIG="$2"; shift 2
        $PYTHON_CMD "$LIB_DIR/consequence_manager.py" add "$DESC" "$TRIG" "$@"
        ;;

    check)
        $PYTHON_CMD "$LIB_DIR/consequence_manager.py" check "$@"
        ;;

    tick)
        $PYTHON_CMD "$LIB_DIR/consequence_manager.py" tick
        ;;

    log)
        $PYTHON_CMD "$LIB_DIR/consequence_manager.py" log
        ;;

    rollback)
        $PYTHON_CMD "$LIB_DIR/consequence_manager.py" rollback
        ;;

    fire)
        if [ "$#" -lt 1 ]; then
            echo "Usage: gm-consequence.sh fire <id> [--reason \"what happened\"]"
            exit 1
        fi
        $PYTHON_CMD "$LIB_DIR/consequence_manager.py" fire "$@"
        ;;

    resolve)
        if [ "$#" -lt 1 ]; then
            echo "Usage: gm-consequence.sh resolve <id>"
            exit 1
        fi
        $PYTHON_CMD "$LIB_DIR/consequence_manager.py" resolve "$1"
        ;;

    list-resolved)
        $PYTHON_CMD "$LIB_DIR/consequence_manager.py" list-resolved
        ;;

    *)
        echo "Unknown action: $ACTION"
        echo "Valid actions: add, check, tick, log, rollback, fire, resolve, list-resolved"
        exit 1
        ;;
esac

# Propagate Python exit code
exit $?
