"""rag/pipelines/ingest_pipeline.py — Orchestrate crawl → process → store pipeline."""

import argparse
import sys
from datetime import date
from pathlib import Path
from typing import Optional

# Allow running from project root without installing as a package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from rag.crawler.config import URL_SECTIONS, QC_DOCS_BASE
from rag.crawler.playwright_crawler import crawl_section_sync
from rag.processing.html_cleaner import HTMLCleaner
from rag.processing.markdown_converter import MarkdownConverter
from rag.processing.chunker import SemanticChunker
from rag.processing.metadata_extractor import MetadataExtractor
from rag.storage.doc_store import DocStore
from rag.storage.bm25_store import BM25Store


class IngestPipeline:
    """Orchestrate the full ingest workflow for one or more QC doc sections.

    Pipeline:
        crawl pages → clean HTML → convert to Markdown → chunk by headers
        → extract metadata → upsert DocStore → rebuild BM25 corpus

    Idempotent: if a URL was already crawled on today's date, it is skipped.
    Re-run with --force to refresh all pages unconditionally.
    """

    def __init__(self) -> None:
        self._cleaner = HTMLCleaner()
        self._converter = MarkdownConverter()
        self._chunker = SemanticChunker()
        self._metadata = MetadataExtractor()
        self._doc_store = DocStore()
        self._bm25_store = BM25Store()

    def run(
        self,
        sections: Optional[list[str]] = None,
        force: bool = False,
    ) -> None:
        """Run the ingest pipeline.

        Args:
            sections: List of section keys to ingest (from URL_SECTIONS).
                      If None, all sections are ingested.
            force: If True, re-crawl and re-index pages regardless of crawl_date.
        """
        # Load existing stores so we can upsert incrementally
        self._doc_store.load()
        self._bm25_store.load()

        target_sections = {
            k: v for k, v in URL_SECTIONS.items()
            if sections is None or k in sections
        }

        if not target_sections:
            print(f"[ingest] No matching sections for: {sections}")
            return

        today = date.today().isoformat()
        total_new = 0

        for section_key, section_path in target_sections.items():
            print(f"\n[ingest] === Section: {section_key} ===")
            pages = crawl_section_sync(section_key, section_path)

            for url, html in pages:
                # Idempotency check
                if not force and self._doc_store.get_crawl_date(url) == today:
                    print(f"[ingest] Skip (already crawled today): {url}")
                    continue

                chunks_added = self._process_page(url, html, section_key)
                total_new += chunks_added
                print(f"[ingest] {url} → {chunks_added} chunks")

        print(f"\n[ingest] Total new chunks: {total_new}")

        if total_new > 0:
            self._doc_store.save()
            print("[ingest] Rebuilding BM25 index…")
            self._bm25_store.build_index(self._doc_store)
            self._bm25_store.save()
            print("[ingest] Done.")
        else:
            print("[ingest] Nothing new to index.")

    # -------------------------------------------------------------------------
    # Private
    # -------------------------------------------------------------------------

    def _process_page(self, url: str, html: str, section_key: str) -> int:
        """Process a single page: clean → convert → chunk → store.

        Returns the number of chunks added.
        """
        clean_html = self._cleaner.clean(html)
        if not clean_html:
            return 0

        markdown = self._converter.convert(clean_html)
        if not markdown.strip():
            return 0

        chunks = self._chunker.chunk_by_headers(markdown)
        section_breadcrumb = [section_key.replace("_", " ").title()]

        for chunk in chunks:
            metadata = self._metadata.extract(
                url=url,
                section_path=section_breadcrumb,
                chunk=chunk,
            )
            self._doc_store.add_doc(
                doc_id=metadata["id"],
                text=chunk["text"],
                metadata=metadata,
            )

        return len(chunks)


# =============================================================================
# CLI entry point
# =============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest QuantConnect docs into the RAG pipeline."
    )
    parser.add_argument(
        "--sections",
        nargs="+",
        metavar="SECTION",
        help=(
            f"Section keys to ingest. Available: {', '.join(URL_SECTIONS.keys())}. "
            "Omit to ingest all sections."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-crawl and re-index pages even if already crawled today.",
    )
    args = parser.parse_args()

    pipeline = IngestPipeline()
    pipeline.run(sections=args.sections, force=args.force)


if __name__ == "__main__":
    main()
