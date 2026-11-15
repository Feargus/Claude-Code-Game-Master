#!/bin/bash
# gm-recall.sh - Semantic recall: the model, and long-term campaign memory
#
#   gm-recall.sh setup                                 # download and check the model (217 MB, once)
#   gm-recall.sh status                                # is semantic recall ready; how much is embedded
#   gm-recall.sh embed                                 # embed this campaign's new texts now (the
#                                                      # background job does this by itself)
#   gm-recall.sh recall "have we met Remex before?"    # keyword recall over plots and facts
#   gm-recall.sh recall "dragon" --top-k 8             # default top-k is 5
#   gm-recall.sh recall "dragon" --provenance our-story
#   gm-recall.sh refresh                               # recompute the old embeddings (RAG deps only)

source "$(dirname "$0")/common.sh"

case "$1" in
    setup)
        $PYTHON_CMD "$LIB_DIR/embedder.py" setup
        exit $?
        ;;
    status)
        $PYTHON_CMD "$LIB_DIR/embedder.py" status || exit 1
        [ -n "$(get_active_campaign)" ] && $PYTHON_CMD "$LIB_DIR/embedding_store.py" status
        exit 0
        ;;
esac

require_active_campaign

if [ "$1" = "embed" ]; then
    $PYTHON_CMD "$LIB_DIR/embedding_store.py" embed
    exit $?
fi

$PYTHON_CMD "$LIB_DIR/campaign_memory.py" "$@"
