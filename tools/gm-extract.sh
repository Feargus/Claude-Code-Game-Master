#!/bin/bash
#
# gm-extract.sh - Preparing a book for play (/import): prepare, the bible and kit,
# the World Index, list, clean. See show_usage.

set -e
source "$(dirname "$0")/common.sh"

# Base directories - use WORLD_STATE_BASE not WORLD_STATE_DIR (which is campaign-specific)
CAMPAIGNS_DIR="$WORLD_STATE_BASE/campaigns"
EXTRACT_DIR="$WORLD_STATE_BASE/extraction-temp"  # Default if no campaign specified

# The campaign a verb operates on: the explicit argument, else the active one.
# A raw `cat active-campaign.txt` used to stand at every call site — under this
# file's `set -e` a missing file made cat return 1 and killed the script with
# zero output, so on a fresh install every verb looked like a silent no-op.
# get_active_campaign (common.sh) always exits 0 and echoes empty when there is
# no campaign, which turns that case into a message.
require_campaign() {
    local campaign_name="$1"
    local verb="$2"
    if [ -z "$campaign_name" ]; then
        campaign_name=$(get_active_campaign)
    fi
    if [ -z "$campaign_name" ]; then
        echo "Error: No campaign specified and no active campaign found." >&2
        echo "  Name one: bash tools/gm-extract.sh $verb <campaign-name>" >&2
        echo "  Or activate one: bash tools/gm-campaign.sh switch <campaign-name> (or run /gm)" >&2
        return 1
    fi
    printf '%s' "$campaign_name"
}

# Directory of an EXISTING campaign. Display names, current slugs and folders
# written under the older slug rule (curse_of_strahd) all resolve through
# lib/campaign_manager.py, which looks at what is actually on disk; re-slugifying
# here would miss the legacy ones and report a real campaign as not found.
# Returns 3 for "no such campaign" and 1 for "the helper could not run at all",
# so `clean` can stay idempotent about the first without swallowing the second.
campaign_dir() {
    local resolved rc=0
    # A campaign is a folder NAME, never a path. "../rag" names a real directory
    # outside campaigns/, and clean would rm -rf it. Refuse loudly here — this is
    # a caller mistake, not "no such campaign".
    case "$1" in
        */*|.|..)
            echo "Error: a campaign is a folder name, not a path: $1" >&2
            return 1
            ;;
    esac
    resolved=$($PYTHON_CMD "$LIB_DIR/campaign_manager.py" resolve "$1" --world-state "$WORLD_STATE_BASE") || rc=$?
    # A non-zero exit is a failure even when something reached stdout: trusting
    # stdout alone would hand back a path built from whatever junk a broken
    # interpreter printed, and clean_temp would rm -rf it. An empty result is
    # just as fatal — joined onto CAMPAIGNS_DIR it resolves to the campaigns
    # ROOT, i.e. every campaign. Refuse rather than guess.
    if [ "$rc" -ne 0 ] || [ -z "$resolved" ]; then
        if [ "$rc" -eq 3 ]; then
            echo "Campaign directory not found for: $1" >&2
            echo "  See what exists: bash tools/gm-campaign.sh list" >&2
            return 3
        fi
        echo "Error: could not derive a campaign slug from: $1" >&2
        echo "  ($PYTHON_CMD could not run lib/campaign_manager.py — run /setup if the venv is missing)" >&2
        return 1
    fi
    printf '%s/%s' "$CAMPAIGNS_DIR" "$resolved"
}

show_usage() {
    cat << EOF
Preparing a book for play (/import)

Commands:
  prepare <file> [name]     Make the book searchable: the campaign folder, the text
                            in source/, the RAG index, chunk files for the World
                            Index's extractor agents. Name defaults to the filename.
  draft-bible [campaign] [--name N] [--voice-json J] [--fields-json J]
                            Draft/refresh the campaign's world-bible.json from
                            current-document.txt (chapter map + verbatim-filtered
                            voice + skeleton keys). Idempotent; refuses a
                            confirmed bible. Run BEFORE draft-ruleset.
  draft-ruleset [campaign] [--force]
                            Draft the World Kit (ruleset.json) from the bible
  campaign-rules [campaign] Write the bible's signature systems into
                            campaign-overview.json as campaign_rules
  write-index [campaign] --index-json J    The World Index: {name, note} per entry
  write-systems [campaign] --systems-json J
  list                      List the campaigns made from a document
  clean [campaign]          Remove a campaign folder (a failed import)

Records are not extracted: they are made when play walks toward someone
(gm-search.sh "<name>" --rag-only, then gm-npc.sh create / gm-location.sh add).

Examples:
  $0 prepare "curse_of_strahd.pdf"
  $0 prepare "module.pdf" "temple-of-evil"
EOF
}

prepare_document() {
    local document="$1"
    local campaign_name="$2"

    if [ -z "$document" ]; then
        echo "Error: Document path required"
        show_usage
        exit 1
    fi

    # common.sh moved us to the project root, so a relative path now has two
    # possible meanings. A human types one relative to their OWN directory
    # (CALLER_PWD). A tool EMITS one relative to the project root — e.g. a
    # world-state/campaigns/<name>/authored-canon.md binder, which is only findable
    # from the root we are already standing in. Try the caller's first (a typed path
    # wins), then the root, and name both when neither is there.
    case "$document" in
        /*) ;;
        *)
            if [ -f "$CALLER_PWD/$document" ]; then
                document="$CALLER_PWD/$document"
            elif [ -f "$PROJECT_ROOT/$document" ]; then
                document="$PROJECT_ROOT/$document"
            else
                echo "Error: File not found: $document"
                echo "  Looked in: $CALLER_PWD/$document"
                echo "  Looked in: $PROJECT_ROOT/$document"
                exit 1
            fi
            ;;
    esac

    if [ ! -f "$document" ]; then
        echo "Error: File not found: $document"
        exit 1
    fi

    # Check for RAG dependencies (sentence-transformers, chromadb)
    if ! $PYTHON_CMD -c "import sentence_transformers; import chromadb" 2>/dev/null; then
        echo "Error: RAG dependencies not installed."
        echo ""
        echo "Install with: uv pip install 'gm-claude[rag]'"
        echo "  or: uv pip install sentence-transformers chromadb"
        exit 1
    fi

    echo "Preparing document for extraction: $document"

    # Build command with optional campaign name
    if [ -n "$campaign_name" ]; then
        echo "Campaign name: $campaign_name"
        $PYTHON_CMD "$LIB_DIR/agent_extractor.py" prepare "$document" --world-state "$WORLD_STATE_BASE" --campaign "$campaign_name"
    else
        $PYTHON_CMD "$LIB_DIR/agent_extractor.py" prepare "$document" --world-state "$WORLD_STATE_BASE"
    fi

    echo
    echo "Document prepared: the book is searchable (gm-search.sh \"...\" --rag-only)."
    echo "Next: /import goes on with the door question and the World Index (Step 5.5)."
}




clean_temp() {
    local campaign_name="$1"

    if [ -n "$campaign_name" ]; then
        echo "Cleaning campaign extraction directory: $campaign_name"
        local rc=0
        CAMPAIGN_DIR=$(campaign_dir "$campaign_name") || rc=$?
        # Cleaning is idempotent: nothing left to remove is the job already done,
        # so a campaign that isn't there (rc 3) exits 0. A helper that could not
        # run (rc 1) is NOT that case — it means we don't know, so it still fails.
        if [ "$rc" -eq 3 ]; then
            exit 0
        elif [ "$rc" -ne 0 ]; then
            exit 1
        fi

        # Last line of defense before an rm -rf: the target's REAL path must be a
        # direct child of the real campaigns dir — never the root itself, never
        # outside the tree. A string compare passed "campaigns/../rag" straight
        # through, so this resolves both sides before comparing.
        local real_target real_campaigns
        real_target=$(cd "$CAMPAIGN_DIR" 2>/dev/null && pwd -P) || real_target=""
        real_campaigns=$(cd "$CAMPAIGNS_DIR" && pwd -P)
        if [ -z "$real_target" ] || [ "$(dirname "$real_target")" != "$real_campaigns" ]; then
            echo "Error: refusing to clean a path outside $CAMPAIGNS_DIR: $CAMPAIGN_DIR" >&2
            exit 1
        fi

        rm -rf "$CAMPAIGN_DIR"
        echo "Cleaned: $CAMPAIGN_DIR"
    else
        echo "Cleaning default extraction temp directory..."
        if [ -d "$EXTRACT_DIR" ]; then
            rm -rf "$EXTRACT_DIR"/*
            echo "Cleaned: $EXTRACT_DIR"
        fi
    fi

    echo "Extraction directory cleared."
}


list_campaigns() {
    echo "Available campaign extractions:"
    echo

    if [ -d "$CAMPAIGNS_DIR" ]; then
        # Use nullglob to handle case where no directories exist
        shopt -s nullglob
        local dirs=("$CAMPAIGNS_DIR"/*/)
        shopt -u nullglob

        for dir in "${dirs[@]}"; do
            if [ -d "$dir" ]; then
                campaign_name=$(basename "$dir")
                if [ -f "$dir/metadata.json" ]; then
                    doc_name=$(jq -r '.document_name // "unknown"' "$dir/metadata.json" 2>/dev/null)
                    date=$(jq -r '.extraction_date // "unknown"' "$dir/metadata.json" 2>/dev/null | cut -d'T' -f1)
                    chunks=$(jq -r '.total_chunks // 0' "$dir/metadata.json" 2>/dev/null)
                    echo "  • $campaign_name"
                    echo "    Document: $doc_name"
                    echo "    Date: $date"
                    echo "    Chunks: $chunks"

                    echo
                fi
            fi
        done
    else
        echo "  No campaigns found."
    fi

    if [ -f "$EXTRACT_DIR/metadata.json" ]; then
        echo "  • [Default extraction]"
        doc_name=$(jq -r '.document_name // "unknown"' "$EXTRACT_DIR/metadata.json" 2>/dev/null)
        echo "    Document: $doc_name"
        echo
    fi
}




# Main command handling
case "$1" in
    prepare)
        prepare_document "$2" "$3"
        ;;



    draft-bible|draft-ruleset|campaign-rules|write-index|write-systems)
        # The bible -> kit -> campaign_rules chain (lib/book_bible.py). The
        # campaign argument is optional here because every flag these verbs take
        # is a --long option: anything starting with -- is passed through, so
        # `draft-bible --name "X"` still means the ACTIVE campaign.
        verb="$1"; shift
        campaign_arg=""
        case "$1" in
            ""|--*) ;;
            *) campaign_arg="$1"; shift ;;
        esac
        campaign_name=$(require_campaign "$campaign_arg" "$verb") || exit 1
        CAMPAIGN_DIR=$(campaign_dir "$campaign_name") || exit 1
        echo "Running $verb: $campaign_name"
        echo "================================="
        $PYTHON_CMD "$LIB_DIR/book_bible.py" "$verb" "$CAMPAIGN_DIR" "$@"
        ;;








    list)
        list_campaigns
        ;;

    clean)
        clean_temp "$2"
        ;;



    *)
        show_usage
        exit 1
        ;;
esac
