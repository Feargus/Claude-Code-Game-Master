#!/usr/bin/env bash
# gm-statusline.sh - Always-on game HUD for the AI Game Master.
#
# Auto-derives a 3-line heads-up display from the active campaign's state
# files (character.json + campaign-overview.json). The agent does NOTHING
# extra: these files are already persisted every turn per the golden rule,
# and Claude Code re-runs this script after every assistant message.
#
# Wired via the project's .claude/settings.json `statusLine` setting, so it
# only overrides the global status line inside this repo.

input=$(cat)  # Claude Code JSON payload on stdin (unused; we read state files)

# Anchor to repo root via this script's location, not cwd.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# 256-color palette (kept light: docs warn multi-line + heavy ANSI can glitch)
GREEN=$'\033[38;5;42m'
AMBER=$'\033[38;5;214m'
RED=$'\033[38;5;203m'
TEAL=$'\033[38;5;51m'
CRED=$'\033[38;5;220m'
DIM=$'\033[38;5;244m'
FAINT=$'\033[38;5;238m'
BOLD=$'\033[1m'
RESET=$'\033[0m'
SEP="${DIM}·${RESET}"
SEPV="${FAINT}│${RESET}"   # vertical segment separator for the vitals line

# Horizontal rule that frames the HUD (drawn both above and below it) to set it
# apart from the conversation above and the input/permissions area below. Width
# auto-detects the terminal; falls back to 80 when stdout is not a tty (the usual
# case for a status-line subprocess). Args let the rule react to danger state:
#   divider [rule_color] [ornament_color]
# Defaults are a calm faint rule with a teal ornament.
divider() {
    local rule="${1:-$FAINT}" orn="${2:-$TEAL}"
    local cols mid half left right
    cols=$(tput cols 2>/dev/null)
    case "$cols" in ''|*[!0-9]*) cols=80 ;; esac
    [ "$cols" -gt 120 ] && cols=120
    [ "$cols" -lt 24  ] && cols=24
    mid="◆"                                  # single-width ornament (no wrap)
    half=$(( (cols - 1) / 2 ))
    printf -v left  '%*s' "$half" '';            left="${left// /─}"
    printf -v right '%*s' "$(( cols - 1 - half ))" ''; right="${right// /─}"
    printf '%s%s%s%s%s%s%s\n' "$rule" "$left" "$orn" "$mid" "$rule" "$right" "$RESET"
}

ACTIVE_FILE="$ROOT/world-state/active-campaign.txt"
if [ ! -f "$ACTIVE_FILE" ] || [ ! -s "$ACTIVE_FILE" ]; then
    divider
    printf '%s⚔ %sGM%s  %sno campaign yet%s  %s  %s%s/gm%s %sto begin — build a world, from one sentence, or from a book%s\n' \
        "$TEAL" "$BOLD" "$RESET" "$DIM" "$RESET" "$SEP" "$BOLD" "$TEAL" "$RESET" "$DIM" "$RESET"
    divider
    exit 0
fi
ACTIVE=$(tr -d '[:space:]' < "$ACTIVE_FILE")

CAMP="$ROOT/world-state/campaigns/$ACTIVE"
CHAR="$CAMP/character.json"
OVER="$CAMP/campaign-overview.json"

if [ ! -f "$CHAR" ]; then
    divider
    printf '%s⚔ %sGM%s  %s%s%s  %sno character yet%s  %s  %s%s/gm%s %sto begin — "who are you in this world?"%s\n' \
        "$TEAL" "$BOLD" "$RESET" "$BOLD" "$ACTIVE" "$RESET" "$DIM" "$RESET" "$SEP" "$BOLD" "$TEAL" "$RESET" "$DIM" "$RESET"
    divider
    exit 0
fi

# --- Character fields -------------------------------------------------------
# The sheet's format: lib/sheet.py. Level N needs 100 × N² XP: the same formula as
# lib/growth.py, repeated here to stay in shell (tests/test_growth.py keeps them in step).
IFS=$'\t' read -r NAME RACE CLASS LEVEL CREDITS XP_CUR XP_NEXT < <(
    jq -r '
      ((.progress.level // 0)) as $level
      | [ (.identity.name // "?"),
          (.identity.race // ""),
          (.identity.role // ""),
          $level,
          (.possessions.credits // 0),
          (.progress.xp // 0),
          (100 * ($level + 1) * ($level + 1))
        ] | @tsv' "$CHAR"
)
LOC="?"

# Conditions array -> status label; fall back to the wound-derived state.
CONDS=$(jq -r '(.status.conditions // []) | map(ascii_downcase) | join(", ")' "$CHAR" 2>/dev/null)

# --- Overview fields (location/time/date) -----------------------------------
DATE="" ; TOD="" ; OLOC=""
if [ -f "$OVER" ]; then
    IFS=$'\t' read -r DATE TOD OLOC < <(
        jq -r '[ (.current_date // ""), (.time_of_day // ""), (.player_position.current_location // "") ] | @tsv' "$OVER"
    )
fi
# Prefer overview's live location if present.
[ -n "$OLOC" ] && LOC="$OLOC"

# --- Wounds ------------------------------------------------------------------
# One line of wounded zones (same words as lib/body.py summary), and a danger
# level: 2 when head, chest or groin has 3 wounds, 1 when any part is injured or
# nearly unusable. A destroyed limb is settled and doesn't keep the HUD amber.
IFS=$'\t' read -r WOUNDS DANGER < <(
    jq -r '
      {head: "head", chest: "chest", groin: "groin", left_arm: "l.arm", right_arm: "r.arm",
       left_leg: "l.leg", right_leg: "r.leg"} as $names
      | ["", "bruised", "injured", "nearly unusable", "destroyed"] as $word
      | (.body.zones // {}) as $body
      | [ $names | keys_unsorted[] | select(($body[.].wounds // 0) > 0)
          | "\($names[.]) \($word[$body[.].wounds])" ] as $parts
      | [ $body | to_entries[] | .key as $zone | (.value.wounds // 0) as $w
          | if (["head", "chest", "groin"] | index($zone)) and $w >= 3 then 2
            elif $w == 2 or $w == 3 then 1 else 0 end ] as $levels
      | [ (if ($parts | length) > 0 then $parts | join(", ") else "unhurt" end),
          ($levels | max // 0) ] | @tsv' "$CHAR"
)

# The danger level drives the color AND the frame: calm when fine, amber when
# injured, a bold red glow when a vital zone is nearly gone.
if   [ "${DANGER:-0}" -eq 0 ]; then WC="$GREEN"; STATE="Normal";   RULEC="$FAINT";        ORNC="$TEAL";          STATEC="$DIM"
elif [ "$DANGER" -eq 1 ];      then WC="$AMBER"; STATE="Wounded";  RULEC="$AMBER";        ORNC="$AMBER";         STATEC="$AMBER"
else                                WC="$RED";   STATE="Critical"; RULEC="${BOLD}${RED}"; ORNC="${BOLD}${RED}";  STATEC="${BOLD}${RED}"
fi
# A named condition (poisoned, etc.) overrides the label but keeps the color.
[ -n "$CONDS" ] && { STATE="$CONDS"; [ "${DANGER:-0}" -eq 0 ] && STATEC="$AMBER"; }

# --- Render (3 lines) -------------------------------------------------------
# Build each line as a string, then emit. Clearer than one packed printf.

L1="${TEAL}⚔ ${BOLD}${NAME}${RESET}  ${DIM}Lv${LEVEL} ${RACE} ${CLASS}${RESET}  ${SEP}  ${AMBER}${LOC}${RESET}"
L2="  ${DIM}Wounds${RESET} ${WC}${WOUNDS}${RESET} ${SEPV} ${CRED}${CREDITS}cr${RESET} ${SEPV} ${DIM}XP${RESET} ${XP_CUR}/${XP_NEXT} ${SEPV} ${STATEC}${STATE}${RESET}"

# Top rule — frames the HUD off from the conversation above.
divider "$RULEC" "$ORNC"

printf '%s\n' "$L1"
printf '%s\n' "$L2"

# Line 3: world clock (only if we have it)
if [ -n "$DATE" ] || [ -n "$TOD" ]; then
    printf '  %s%s %s %s%s\n' "$DIM" "$DATE" "$SEP" "$TOD" "$RESET"
fi

# Closing rule — separates the HUD from the input / permissions area below.
divider "$RULEC" "$ORNC"
