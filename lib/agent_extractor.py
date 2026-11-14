#!/usr/bin/env python3
"""
Preparing a book for play (`gm-extract.sh prepare`): the campaign folder, the
document's text kept in source/, the RAG index (vectors/) that gm-search.sh and
gm-enhance.sh read, and chunk files the extractor agents read for the World
Index (/import, Step 5.5).

Upstream also merged the agents' full records into the campaign (merge, save,
review: the "census"). That is gone (2026-11-11): records are made when play
walks toward someone, with gm-npc.sh create.
"""

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from lib.campaign_manager import CampaignManager
from lib.json_ops import JsonOperations

# RAG imports - required, no fallback
from lib.rag import check_rag_available, get_missing_deps


class AgentExtractor:
    """Coordinates concurrent agent extraction of story content"""

    def __init__(self, world_state_dir: str = "world-state", campaign_name: str = None):
        self.world_state_dir = Path(world_state_dir)
        self.campaigns_dir = self.world_state_dir / "campaigns"
        self.campaign_name = campaign_name

        # Set extraction directory based on campaign
        if campaign_name:
            self.extraction_dir = self.campaigns_dir / self._sanitize_name(campaign_name)
        else:
            self.extraction_dir = self.world_state_dir / "extraction-temp"

        # Initialize managers
        self.json_ops = JsonOperations(world_state_dir)
        self.campaign_manager = CampaignManager(world_state_dir)

        # RAG extractor initialized lazily in prepare_for_agents
        self._rag_extractor = None

        # Backup of existing campaign data (preserved before extraction)
        self._existing_backup = {}

        # Ensure extraction directory exists
        self.extraction_dir.mkdir(parents=True, exist_ok=True)
        (self.extraction_dir / "chunks").mkdir(exist_ok=True)
        (self.extraction_dir / "extracted").mkdir(exist_ok=True)

    def _backup_existing_data(self) -> dict[str, Any]:
        """Backup existing campaign data before extraction.

        This preserves NPCs, locations, facts, items, and plots that were
        created manually or from previous imports so they aren't lost.
        """
        backup = {}
        files_to_backup = ['npcs.json', 'locations.json', 'facts.json', 'items.json', 'plots.json', 'consequences.json']

        for filename in files_to_backup:
            filepath = self.extraction_dir / filename
            if filepath.exists():
                try:
                    with open(filepath, encoding='utf-8') as f:
                        data = json.load(f)
                    # Only backup if there's actual content
                    if data and (isinstance(data, dict) and len(data) > 0) or (isinstance(data, list) and len(data) > 0):
                        backup[filename] = data
                        print(f"  Backed up existing {filename} ({len(data) if isinstance(data, dict) else 'list'} entries)")
                except (OSError, json.JSONDecodeError) as e:
                    print(f"  Warning: Could not backup {filename}: {e}")

        return backup

    def prepare_for_agents(self, filepath: str) -> dict[str, Any]:
        """
        Extract text and vectorize document for agent extraction and /enhance.

        Returns dict with:
        - document_name: Source document
        - campaign_folder: Where content is being extracted
        - total_chunks: Number of chunks created
        - metadata: Additional info
        """
        # Check RAG availability - required, no fallback
        if not check_rag_available():
            missing = get_missing_deps()
            print("ERROR: RAG dependencies not installed.")
            print(f"Missing: {', '.join(missing)}")
            print("Install with: uv pip install -e '.[rag]'")
            print("Or: pip install sentence-transformers chromadb")
            sys.exit(1)

        # Import RAG components (safe now that we checked availability)
        from lib.rag import RAGExtractor

        print(f"Preparing document: {filepath}")

        # Set campaign name from document if not already set
        if not self.campaign_name:
            self.campaign_name = Path(filepath).stem
            self.extraction_dir = self.campaigns_dir / self._sanitize_name(self.campaign_name)
            self.extraction_dir.mkdir(parents=True, exist_ok=True)
            (self.extraction_dir / "chunks").mkdir(exist_ok=True)
            (self.extraction_dir / "extracted").mkdir(exist_ok=True)

        print(f"Campaign folder: {self.extraction_dir}")

        # Ensure campaign_name is sanitized (in case it was passed to __init__)
        sanitized_name = self._sanitize_name(self.campaign_name)

        # BACKUP existing data BEFORE initializing (prevents data loss on re-import)
        self._existing_backup = self._backup_existing_data()
        if self._existing_backup:
            print(f"  Preserved {len(self._existing_backup)} existing data files for merge")

        # Initialize full campaign structure with preserve_existing=True
        # This ensures we don't overwrite existing files
        display_name = sanitized_name.replace('-', ' ').title()
        self.campaign_manager.init_campaign_files(
            self.extraction_dir,
            f"{display_name} Campaign",
            preserve_existing=True
        )

        # Clear previous extraction temp files (chunks, extracted) but not world state
        self._clear_extraction_temp()

        # Initialize RAG extractor for this campaign
        self._rag_extractor = RAGExtractor(str(self.extraction_dir))

        # Extract and vectorize document (no categorization - all chunks stored uniformly)
        rag_metadata = self._rag_extractor.extract_from_document(filepath, clear_existing=True)

        # Save the full text for reference
        from lib.content_extractor import ContentExtractor
        extractor = ContentExtractor()
        full_text = extractor.extract_text(filepath)
        source_dir = self.extraction_dir / "source"
        source_dir.mkdir(exist_ok=True)
        (source_dir / "current-document.txt").write_text(full_text)

        # Write chunks to files for extraction agents to read
        chunks = self._rag_extractor._split_into_chunks(full_text)
        self._write_chunk_files(chunks)

        # Create metadata
        metadata = {
            "source_file": filepath,
            "document_name": Path(filepath).stem,
            "extraction_date": datetime.now().isoformat(),
            "extraction_method": "rag",
            "total_chunks": rag_metadata.get("total_chunks", 0),
            "total_chars": rag_metadata.get("total_chars", 0),
            "chunk_size": rag_metadata.get("chunk_size", 3000),
            "rag_stats": self._rag_extractor.get_stats()
        }

        # Save metadata
        (self.extraction_dir / "metadata.json").write_text(
            json.dumps(metadata, indent=2, default=str)
        )

        return {
            "document_name": metadata["document_name"],
            "campaign_folder": str(self.extraction_dir),
            "total_chunks": metadata["total_chunks"],
            "metadata": metadata
        }

    def _write_chunk_files(self, chunks: list) -> dict:
        """Write chunks to files for extraction agents to read."""
        chunk_dir = self.extraction_dir / "chunks"
        chunk_dir.mkdir(exist_ok=True)

        chunk_files = []
        for idx, chunk_text in enumerate(chunks):
            filename = f"chunk_{idx:03d}.txt"
            filepath = chunk_dir / filename

            # Add header to chunk
            header = f"# Chunk {idx + 1} of {len(chunks)}\n"
            header += "---\n\n"

            filepath.write_text(header + chunk_text)
            chunk_files.append(str(filepath))

        print(f"  Wrote {len(chunk_files)} chunk files to {chunk_dir}")
        return {"chunk_files": chunk_files, "total_chunks": len(chunks)}

    def _clear_extraction_temp(self):
        """Clear the extraction temp directory (before extraction)"""
        for subdir in ['chunks', 'extracted']:
            dir_path = self.extraction_dir / subdir
            if dir_path.exists():
                shutil.rmtree(dir_path)
            dir_path.mkdir(exist_ok=True)

    def _sanitize_name(self, name: str) -> str:
        """Sanitize a campaign name for use as a directory name.

        Straight through to CampaignManager._slugify — the one slug rule, so
        extraction and campaign creation always agree on the directory. Do NOT
        stem here: a campaign named "Curse of Strahd v2.0" would lose its ".0"
        and land in a second directory. Callers that pass a *filepath* stem it
        themselves (see prepare_for_agents).
        """
        return CampaignManager._slugify(name)


def main():
    """CLI interface for agent extraction"""
    import sys

    if len(sys.argv) < 2:
        print("Usage: agent_extractor.py prepare <document> [--campaign name] [--world-state dir]")
        sys.exit(1)

    def take_flag(flag):
        """Pull `--flag value` out of argv so the positional parsing below is
        unaffected by it. Returns the value, or None when the flag is absent."""
        if flag not in sys.argv:
            return None
        idx = sys.argv.index(flag)
        if idx + 1 >= len(sys.argv):
            return None
        value = sys.argv[idx + 1]
        sys.argv.pop(idx)
        sys.argv.pop(idx)
        return value

    campaign_name = take_flag('--campaign')
    # Which world-state tree this run reads and writes. The default is RELATIVE,
    # so with common.sh having cd'd to the project root it means the live tree —
    # every wrapper therefore passes its own WORLD_STATE_BASE (the seam
    # GM_WORLD_STATE_BASE moves), the same way gm-extract.sh's other verbs hand
    # their manager an explicit path.
    world_state_dir = take_flag('--world-state') or "world-state"

    extractor = AgentExtractor(world_state_dir=world_state_dir, campaign_name=campaign_name)
    command = sys.argv[1]

    if command == "prepare" and len(sys.argv) > 2:
        # Prepare document for extraction
        filepath = sys.argv[2]
        result = extractor.prepare_for_agents(filepath)
        print(json.dumps(result, indent=2))

    else:
        print(f"Unknown command: {command}")
        print("Usage: agent_extractor.py prepare <document> [--campaign name]")


if __name__ == "__main__":
    main()
