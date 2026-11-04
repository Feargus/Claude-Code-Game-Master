#!/bin/bash
# gm-body.sh - Wounds, armor and cyberware of the player (wrapper for body.py)

source "$(dirname "$0")/common.sh"

if [ "$#" -lt 1 ]; then
    echo "Usage: gm-body.sh show"
    echo "       gm-body.sh hit ZONE [WOUNDS]                 # armor first, then flesh or chrome"
    echo "       gm-body.sh heal ZONE [WOUNDS]"
    echo "       gm-body.sh note ZONE \"TEXT\"                  # the story of the wounds; \"\" clears"
    echo "       gm-body.sh armor NAME ZONE:BOXES... [--dr N]  # worn on the outside"
    echo "       gm-body.sh cyberware NAME ZONE BOXES [--effect \"TEXT\"]"
    echo "       gm-body.sh repair NAME"
    echo "       gm-body.sh remove NAME"
    echo ""
    echo "Zones: head, chest, groin, left_arm, right_arm, left_leg, right_leg"
    exit 1
fi

require_active_campaign

$PYTHON_CMD "$LIB_DIR/body.py" "$@"
