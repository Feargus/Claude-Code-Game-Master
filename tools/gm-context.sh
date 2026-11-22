#!/bin/bash
# gm-context.sh - Unified scene context (one front door for search/enhance/scene)
#
# Usage:
#   gm-context.sh                          Context for the current location
#   gm-context.sh "Over City Village"      Context for a specific location
#   gm-context.sh "Warehouse" --entity "Mordecai" --entity "Katia"
#
# Returns world-state facts (location, NPCs present, named entities) plus grounded
# source passages from RAG when the campaign has a vector store.

source "$(dirname "$0")/common.sh"

require_active_campaign

$PYTHON_CMD "$LIB_DIR/scene_context.py" "$@"
