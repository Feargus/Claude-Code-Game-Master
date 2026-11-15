#!/bin/bash
# gm-recall.sh - Semantic recall: the model and the campaign's embeddings
#
#   gm-recall.sh setup      download and check the model (217 MB, once)
#   gm-recall.sh status     is semantic recall ready; how much of the campaign is embedded
#   gm-recall.sh embed      embed the campaign's new texts now (a background job does
#                           this by itself after each command that records them)
#   gm-recall.sh stop       stop the helper that keeps the model loaded (it starts by
#                           itself when needed and stops after 30 minutes unused)
#
# Recall itself: gm-note.sh find --like "<question>"

source "$(dirname "$0")/common.sh"

case "$1" in
    setup)
        $PYTHON_CMD "$LIB_DIR/embedder.py" setup
        exit $?
        ;;
    status)
        $PYTHON_CMD "$LIB_DIR/embedder.py" status || exit 1
        $PYTHON_CMD "$LIB_DIR/embed_helper.py" status
        [ -n "$(get_active_campaign)" ] && $PYTHON_CMD "$LIB_DIR/embedding_store.py" status
        exit 0
        ;;
    stop)
        $PYTHON_CMD "$LIB_DIR/embed_helper.py" stop
        exit $?
        ;;
esac

require_active_campaign

if [ "$1" = "embed" ]; then
    $PYTHON_CMD "$LIB_DIR/embedding_store.py" embed
    exit $?
fi

if [ "$1" = "recall" ]; then
    echo "[ERROR] gm-recall.sh recall is gone: gm-note.sh find --like \"<question>\" ranks the facts by meaning." >&2
    exit 1
fi
echo "Usage: gm-recall.sh setup | status | embed   (recall: gm-note.sh find --like \"<question>\")" >&2
exit 1
