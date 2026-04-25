"""rag/storage/bm25_store.py — BM25 keyword index over the DocStore corpus."""

import json
import re
from pathlib import Path
from typing import Any, Optional

from rag.crawler.config import BM25_CORPUS_PATH


class BM25Store:
    """Wrap rank_bm25.BM25Okapi with load/save support.

    The tokenized corpus is persisted to disk so the index can be rebuilt
    without re-crawling. Rebuild the index whenever doc_store changes by
    calling build_index() followed by save().
    """

    def __init__(self, path: Path = BM25_CORPUS_PATH) -> None:
        self._path = path
        self._bm25 = None
        self._doc_ids: list[str] = []
        self._tokenized_corpus: list[list[str]] = []

    # -------------------------------------------------------------------------
    # Index construction
    # -------------------------------------------------------------------------

    def build_index(self, doc_store) -> None:
        """Tokenize all chunks in DocStore and build the BM25 index.

        Args:
            doc_store: DocStore instance (must be loaded)
        """
        from rank_bm25 import BM25Okapi  # noqa: PLC0415

        docs = doc_store.list_all()
        self._doc_ids = [d["id"] for d in docs]
        self._tokenized_corpus = [self._tokenize(d["text"]) for d in docs]
        self._bm25 = BM25Okapi(self._tokenized_corpus)
        print(f"[bm25_store] Built index over {len(self._doc_ids)} chunks")

    # -------------------------------------------------------------------------
    # Search
    # -------------------------------------------------------------------------

    def search(
        self, query: str, doc_store, top_k: int = 5
    ) -> list[dict[str, Any]]:
        """Score query against corpus and return top-k results.

        Args:
            query: Natural language or keyword query string
            doc_store: DocStore instance (for retrieving text/metadata)
            top_k: Number of results to return

        Returns:
            List of dicts: {doc_id, score, text, metadata}, sorted by score desc
        """
        if self._bm25 is None:
            raise RuntimeError("BM25 index not built. Call build_index() or load() first.")

        tokens = self._tokenize(query)
        scores = self._bm25.get_scores(tokens)

        # Pair scores with doc IDs, sort descending
        ranked = sorted(
            zip(scores, self._doc_ids),
            key=lambda x: x[0],
            reverse=True,
        )

        results = []
        for score, doc_id in ranked[:top_k]:
            doc = doc_store.get_doc(doc_id)
            if doc:
                results.append({
                    "doc_id": doc_id,
                    "score": float(score),
                    "text": doc["text"],
                    "metadata": doc.get("metadata", {}),
                })

        return results

    # -------------------------------------------------------------------------
    # Persistence
    # -------------------------------------------------------------------------

    def save(self) -> None:
        """Persist the tokenized corpus and doc IDs to disk.

        Avoids expensive re-tokenization on every query.
        The BM25 object itself is NOT serialized — it is rebuilt from the
        saved corpus on load().
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "doc_ids": self._doc_ids,
            "tokenized_corpus": self._tokenized_corpus,
        }
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        print(f"[bm25_store] Saved corpus ({len(self._doc_ids)} docs) → {self._path}")

    def load(self) -> None:
        """Restore corpus from disk and rebuild the BM25 object.

        No-op if file does not exist.
        """
        if not self._path.exists():
            return

        from rank_bm25 import BM25Okapi  # noqa: PLC0415

        with open(self._path, encoding="utf-8") as f:
            payload = json.load(f)

        self._doc_ids = payload["doc_ids"]
        self._tokenized_corpus = payload["tokenized_corpus"]
        self._bm25 = BM25Okapi(self._tokenized_corpus)
        print(f"[bm25_store] Loaded corpus ({len(self._doc_ids)} docs) ← {self._path}")

    # -------------------------------------------------------------------------
    # Private
    # -------------------------------------------------------------------------

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Lowercase, split on non-alphanumeric characters, drop short tokens."""
        tokens = re.split(r"[^a-z0-9_]+", text.lower())
        return [t for t in tokens if len(t) > 1]
