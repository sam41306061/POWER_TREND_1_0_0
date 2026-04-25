"""rag/processing/metadata_extractor.py — Extract metadata from crawled chunks."""

import hashlib
from datetime import date
from typing import Any
from urllib.parse import urlparse


class MetadataExtractor:
    """Build the metadata dict for each document chunk.

    Schema matches the spec in docs/AI_RAG_STRUCTURE.md.
    """

    def extract(
        self,
        url: str,
        section_path: list[str],
        chunk: dict[str, Any],
        crawl_date: date | None = None,
    ) -> dict[str, Any]:
        """Build metadata for one chunk.

        Args:
            url: Canonical page URL
            section_path: Breadcrumb path from root to current H2/H3 header
            chunk: Output dict from SemanticChunker (contains header_path, text)
            crawl_date: Date of crawl; defaults to today

        Returns:
            Metadata dict conforming to AI_RAG_STRUCTURE.md schema
        """
        if crawl_date is None:
            crawl_date = date.today()

        header_path: list[str] = chunk.get("header_path", [])
        full_section = section_path + header_path

        doc_id = self._make_id(url, header_path)

        return {
            "id": doc_id,
            "source": "quantconnect-docs",
            "doc_version": "v2",
            "url": url,
            "section_path": full_section,
            "language": self._detect_language(url),
            "platform": self._detect_platform(url),
            "confidence": 1.0,
            "crawl_date": crawl_date.isoformat(),
        }

    # -------------------------------------------------------------------------
    # Private
    # -------------------------------------------------------------------------

    @staticmethod
    def _make_id(url: str, header_path: list[str]) -> str:
        """Generate a stable SHA-256 ID from url + header path."""
        raw = url + "|".join(header_path)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    @staticmethod
    def _detect_language(url: str) -> str:
        """Infer language from URL query params or path; default to python."""
        path = urlparse(url).path.lower()
        if "csharp" in path or "c-sharp" in path:
            return "csharp"
        return "python"

    @staticmethod
    def _detect_platform(url: str) -> str:
        """Infer platform from URL; default to cloud."""
        path = urlparse(url).path.lower()
        if "lean-cli" in path or "lean-engine" in path or "local" in path:
            return "lean-cli"
        return "cloud"
