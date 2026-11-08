#!/bin/bash
# gm-consequence.sh - Consequence tracking (thin wrapper for consequence_manager.py)

source "$(dirname "$0")/common.sh"

usage() {
    cat <<'TEXT'
Usage: gm-consequence.sh <action> [args]

Actions:
  add "<what happens>" "<trigger in words>" [triggers] [effects]
                                 - Add a consequence
  tick                           - Fire consequences matching the current scene (auto on move/time)
  check                          - List pending consequences
  fire <id> [--by <fact id>] [--reason "..."]
                                 - Fire a consequence by hand (its condition happened)
  resolve <id>                   - Resolve a consequence (once it has played out)
  log / rollback                 - Why things fired / undo the last firing
  list-resolved                  - List resolved consequences
  (an id may be shortened to a unique prefix, e.g. the 4 characters the brief shows)

add:
  "<what happens>"      the text the GM sees when it fires
  "<trigger in words>"  for people reading it; no script matches on it. Without
                        --trigger-type it becomes an on_event trigger: every fact
                        recorded lists it, and the GM fires it by judgment
  Triggers (repeat --trigger-type/--match pairs; any one fires it):
    --trigger-type on_location --match "<place>"         (a known place, exactly)
    --trigger-type on_npc      --match "<NPC>"           (a known NPC, in the scene)
    --trigger-type on_time     --match night             (a time-of-day word, not a date)
    --trigger-type on_death    --match "<NPC>" | player
  Places and NPCs are stored as ids (location:<name>, npc:<name>); add new ones first.
    --trigger-type on_clock    --match "<clock>" | "<clock>:<segment>"
    --trigger-type on_learn    --match "<who> learns <fact id>" | "<who> learns about <id>"
    --trigger-type on_event    --match "<the event, in words>"
  A time limit ("in 2 days") is a clock (gm-clock.sh add), not a trigger.
  Effects, carried out when it fires:
    --starts-clock "<name>" [--clock-segments N] [--clock-on time|event]
                   [--clock-due-in 3d | --clock-due "YYYY-MM-DD HH:MM"] [--clock-consequence "..."]
    --tells <fact id> --to <holder> [--to <holder>...]

Examples:
  gm-consequence.sh add "Dekker's crew leans on Auntie Ro" "next time he's at the stall" \
      --trigger-type on_location --match "The Lantern noodle stall"
  gm-consequence.sh add "The tracker arrives" "the tracker clock runs out" \
      --trigger-type on_clock --match "Tracker"
  gm-consequence.sh add "Footprints at the door" "the tracker is halfway" \
      --trigger-type on_clock --match "Tracker:2"
  gm-consequence.sh add "Word gets out" "the job goes loud" \
      --starts-clock "Vendetta" --clock-segments 3 --clock-on event
  gm-consequence.sh add "The Palimpsest hunt him" "they hear of him" \
      --trigger-type on_learn --match "npc:Sister Lacuna learns about player"
  gm-consequence.sh add "The witness reaches the Palimpsest" "the Witness clock runs out" \
      --trigger-type on_clock --match "Witness" --tells f42 --to "npc:Sister Lacuna"
  gm-consequence.sh add "The Fork bargains" "someone is alone with the chip" \
      --trigger-type on_event --match "someone is alone with the chip"
  gm-consequence.sh fire ab12 --by f17
  gm-consequence.sh resolve ab12
TEXT
}

if [ "$#" -lt 1 ]; then
    usage
    exit 1
fi

require_active_campaign

ACTION="$1"
shift

case "$ACTION" in
    add)
        if [ "$#" -lt 2 ]; then
            usage
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
