"""rag/storage/doc_store.py — JSON-backed persistence for all crawled chunks."""

import json
from pathlib import Path
from typing import Any, Optional

from rag.crawler.config import DOC_STORE_PATH


class DocStore:
    """Persist and retrieve document chunks as a flat JSON store.

    Each entry is keyed by the chunk's metadata ID (SHA-256 prefix) and contains
    both the chunk text and the full metadata dict.
    """

    def __init__(self, path: Path = DOC_STORE_PATH) -> None:
        self._path = path
        self._store: dict[str, dict[str, Any]] = {}

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------

    def add_doc(self, doc_id: str, text: str, metadata: dict[str, Any]) -> None:
        """Insert or replace a document chunk.

        Args:
            doc_id: Unique chunk ID (from MetadataExtractor)
            text: Chunk plain text
            metadata: Full metadata dict
        """
        self._store[doc_id] = {"id": doc_id, "text": text, "metadata": metadata}

    def get_doc(self, doc_id: str) -> Optional[dict[str, Any]]:
        """Retrieve a chunk by ID. Returns None if not found."""
        return self._store.get(doc_id)

    def list_all(self) -> list[dict[str, Any]]:
        """Return all stored chunks as a list."""
        return list(self._store.values())

    def __len__(self) -> int:
        return len(self._store)

    # -------------------------------------------------------------------------
    # Persistence
    # -------------------------------------------------------------------------

    def save(self) -> None:
        """Write the full store to disk as JSON."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._store, f, ensure_ascii=False, indent=2)
        print(f"[doc_store] Saved {len(self._store)} chunks → {self._path}")

    def load(self) -> None:
        """Load the store from disk. No-op if file does not exist."""
        if not self._path.exists():
            return
        with open(self._path, encoding="utf-8") as f:
            self._store = json.load(f)
        print(f"[doc_store] Loaded {len(self._store)} chunks ← {self._path}")

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def get_crawl_date(self, url: str) -> Optional[str]:
        """Return the crawl_date for the most recent chunk from a given URL.

        Used by IngestPipeline for idempotent skip logic.
        """
        for doc in self._store.values():
            if doc.get("metadata", {}).get("url") == url:
                return doc["metadata"].get("crawl_date")
        return None

    def texts(self) -> list[str]:
        """Return a flat list of all chunk texts (in insertion order)."""
        return [doc["text"] for doc in self._store.values()]

    def ids(self) -> list[str]:
        """Return all chunk IDs in insertion order."""
        return list(self._store.keys())
