#!/bin/bash
# gm-glossary.sh - The world's own terms (wrapper for glossary.py)
#
#   gm-glossary.sh list                                 every term with its meaning
#   gm-glossary.sh show "<term>"                        one term's meaning
#   gm-glossary.sh add "<term>" "<what it means here>"  a new term: a thing, an institution, slang
#   gm-glossary.sh describe "<term>" "<new meaning>"    reword it (the term stays)

source "$(dirname "$0")/common.sh"

if [ "$#" -lt 1 ] || [ "$1" = "help" ] || [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    sed -n '3,7p' "$0" | sed 's/^# \{0,1\}//'
    exit 0
fi

require_active_campaign

$PYTHON_CMD "$LIB_DIR/glossary.py" "$@"
