#!/usr/bin/env python3
"""
Book indexing: a campaign's source book cut into pieces, made searchable by meaning.

1. Extract the text from the document (PDF, DOCX, TXT, ...)
2. Split it into pieces of about 1,500 characters, at headings and paragraphs
   (the model reads at most 512 tokens per text; 3,000 characters lost a quarter)
3. Store the pieces (vectors/chunks.json)
4. A background job embeds them with the facts' model (vector_store.index_job):
   about 15 to 30 minutes for a novel on a Raspberry Pi 4. Nothing that searches the
   book runs before it is done (gm-extract.sh wait). A book indexed for one campaign
   is copied for the next, in seconds (vector_store.from_shared).

No categorization: all pieces are stored alike and found by closeness to the question.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from lib.rag.vector_store import CampaignVectorStore, start_index_job


class RAGExtractor:
    """Book indexing for semantic search."""

    DEFAULT_CHUNK_SIZE = 1500

    def __init__(self, campaign_dir: str, chunk_size: int = None, embedder=None):
        """`embedder`: one to index with at once (tests); without it, a background
        job does the indexing (start_index_job)."""
        self.campaign_dir = Path(campaign_dir)
        self.chunk_size = chunk_size or self.DEFAULT_CHUNK_SIZE
        self.embedder = embedder
        self.vector_store = CampaignVectorStore(campaign_dir)
        self._document_name: str | None = None
        self._extraction_metadata: dict = {}

    def extract_from_document(self, filepath: str, clear_existing: bool = False) -> dict[str, Any]:
        """Cut the document into pieces and store them; the vectors are made in the
        background (or here, with the embedder given). Replaces an earlier book."""
        filepath = Path(filepath)
        self._document_name = filepath.stem
        print(f"Book indexing: {filepath.name}")
        print("=" * 50)
        print("Step 1: Extracting text from document...")
        raw_text = self._extract_text(filepath)
        print(f"  Extracted {len(raw_text):,} characters")
        print("Step 2: Splitting into pieces...")
        chunks = self._split_into_chunks(raw_text)
        print(f"  {len(chunks)} pieces of about {self.chunk_size:,} characters")
        print("Step 3: Storing the pieces...")
        from lib.rag.vector_store import book_key
        key = book_key(raw_text, self.chunk_size)
        if self.embedder is None and self.vector_store.from_shared(key):
            self.vector_store.set_source(key, self._document_name)
            print("Step 4: already indexed for an earlier campaign: copied.")
            indexing = "done (from an earlier campaign)"
        else:
            self.vector_store.set_chunks(
                chunks, [{"chunk_index": i, "document": self._document_name} for i in range(len(chunks))],
                [f"doc_{i:04d}" for i in range(len(chunks))])
            self.vector_store.set_source(key, self._document_name)
            indexing = self._index(len(chunks))
        self._extraction_metadata = {
            "source_file": str(filepath), "document_name": self._document_name,
            "extraction_date": datetime.now().isoformat(), "total_chars": len(raw_text),
            "total_chunks": len(chunks), "chunk_size": self.chunk_size, "indexing": indexing,
        }
        return self._extraction_metadata

    def _index(self, pieces: int) -> str:
        if self.embedder is not None:
            print("Step 4: Embedding the pieces...")
            self.vector_store.index(self.embedder)
            self.vector_store.share()
            return "done"
        if start_index_job(self.campaign_dir):
            minutes = max(1, round(pieces * 4 / 60))
            print(f"Step 4: Embedding the pieces in the background, about {minutes} min. Nothing "
                  f"that searches the book runs before it is done: bash tools/gm-extract.sh wait")
            return "in the background"
        print("Step 4: skipped: semantic recall isn't installed (bash tools/gm-recall.sh "
              "status); the pieces are stored and will be embedded once it is")
        return "waiting for semantic recall"

    def query(
        self,
        query_text: str,
        n_results: int = 20
    ) -> list[dict]:
        """
        Query the vector store by semantic similarity.

        Args:
            query_text: Text to search for
            n_results: Maximum number of results

        Returns:
            List of chunk dicts with 'text', 'metadata', 'distance'
        """
        from embedder import get_embedder
        results = self.vector_store.query_by_text(
            query_text,
            self.embedder or get_embedder(),
            n_results=n_results
        )

        # Format results
        formatted = []
        for i in range(len(results["documents"])):
            formatted.append({
                "text": results["documents"][i],
                "metadata": results["metadatas"][i],
                "distance": results["distances"][i] if results["distances"] else 0.0
            })

        return formatted

    def get_extraction_metadata(self) -> dict:
        """Get metadata about the last extraction."""
        return self._extraction_metadata.copy()

    def get_stats(self) -> dict:
        """Get current statistics."""
        return {
            "campaign_dir": str(self.campaign_dir),
            "vector_store": self.vector_store.get_stats(),
            "extraction": self._extraction_metadata,
        }

    def _extract_text(self, filepath: Path) -> str:
        """Extract text from a document file."""
        from lib.content_extractor import ContentExtractor

        extractor = ContentExtractor()
        return extractor.extract_text(str(filepath))

    def _split_into_chunks(self, text: str) -> list[str]:
        """Split text into chunks of approximately chunk_size characters."""
        chunks = []

        # Try to split by headers first (markdown or common patterns)
        header_pattern = r'^(?:#{1,3}\s+.+|[A-Z][A-Z\s]+:|Chapter \d+|PART [IVX]+)'
        sections = re.split(f'({header_pattern})', text, flags=re.MULTILINE)

        current_chunk = ""

        for section in sections:
            if not section.strip():
                continue

            if len(current_chunk) + len(section) > self.chunk_size:
                if current_chunk:
                    chunks.append(current_chunk.strip())

                # If section itself is too large, split it further
                if len(section) > self.chunk_size:
                    sub_chunks = self._split_by_paragraphs(section)
                    chunks.extend(sub_chunks[:-1])  # Add all but last
                    current_chunk = sub_chunks[-1] if sub_chunks else ""
                else:
                    current_chunk = section
            else:
                current_chunk += section

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        # If we got very few chunks, fall back to paragraph splitting
        if len(chunks) <= 1 and len(text) > self.chunk_size:
            chunks = self._split_by_paragraphs(text)

        return chunks

    def _split_by_paragraphs(self, text: str) -> list[str]:
        """Split text by paragraphs, respecting chunk size."""
        chunks = []
        paragraphs = text.split('\n\n')

        current_chunk = ""

        for para in paragraphs:
            if len(current_chunk) + len(para) > self.chunk_size:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para
            else:
                current_chunk += "\n\n" + para if current_chunk else para

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks


def main():
    """CLI for RAG extraction."""
    import json
    import sys
    import tempfile

    if len(sys.argv) < 2:
        print("Usage: rag_extractor.py <filepath> [campaign_dir]")
        print("\nVectorizes a document for semantic search with /enhance.")
        sys.exit(1)

    filepath = sys.argv[1]
    campaign_dir = sys.argv[2] if len(sys.argv) > 2 else tempfile.mkdtemp()

    print(f"Document: {filepath}")
    print(f"Campaign: {campaign_dir}")
    print()

    extractor = RAGExtractor(campaign_dir)
    extractor.extract_from_document(filepath)

    print("\n" + "=" * 50)
    print("Stats:")
    print(json.dumps(extractor.get_stats(), indent=2, default=str))


if __name__ == "__main__":
    main()
