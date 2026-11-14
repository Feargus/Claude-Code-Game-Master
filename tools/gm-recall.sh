#!/bin/bash
# gm-recall.sh - Long-term campaign memory: recall over the plots and facts
#
#   gm-recall.sh recall "have we met Remex before?"   # semantic when RAG deps present, keyword fallback
#   gm-recall.sh recall "dragon" --top-k 8            # default top-k is 5
#   gm-recall.sh recall "dragon" --provenance our-story
#   gm-recall.sh refresh                               # recompute the embeddings for semantic recall
#                                                      # (only with the RAG deps; keyword recall needs none)

source "$(dirname "$0")/common.sh"

require_active_campaign

$PYTHON_CMD "$LIB_DIR/campaign_memory.py" "$@"
