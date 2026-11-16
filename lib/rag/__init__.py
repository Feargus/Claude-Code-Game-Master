"""
Book search: a campaign's source book, searchable by meaning.

It uses the same model as the facts' semantic recall (lib/embedder.py:
EmbeddingGemma on ONNX Runtime) and stores its pieces and vectors in the
campaign's vectors/ folder (vector_store.py). Install: `uv sync --extra recall`,
then `bash tools/gm-recall.sh setup` for the model. Without them the rest of the
game works; only the book search is off.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def get_missing_deps() -> list:
    """What semantic recall still needs: packages, or the model files."""
    from embedder import files_missing, packages_missing
    missing = packages_missing()
    if not missing and files_missing():
        missing = ["the model files (bash tools/gm-recall.sh setup)"]
    return missing


def check_rag_available() -> bool:
    """The book search can embed (packages and model installed)."""
    return not get_missing_deps()


RAG_AVAILABLE = check_rag_available()


def require_rag():
    """Raise an error if the book search can't run."""
    missing = get_missing_deps()
    if missing:
        raise ImportError(f"The book search needs {', '.join(missing)}: uv sync --extra recall, "
                          f"then bash tools/gm-recall.sh setup")


from lib.rag.rag_extractor import RAGExtractor  # noqa: E402
from lib.rag.vector_store import CampaignVectorStore  # noqa: E402

__all__ = ["RAG_AVAILABLE", "check_rag_available", "get_missing_deps", "require_rag",
           "RAGExtractor", "CampaignVectorStore"]
