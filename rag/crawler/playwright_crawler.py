"""rag/crawler/playwright_crawler.py — Async QC docs crawler using Playwright."""

import asyncio
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

from rag.crawler.config import MAX_PAGES_PER_SECTION, QC_DOCS_BASE, RAW_DIR, REQUEST_DELAY
from rag.crawler.url_queue import URLQueue


class PlaywrightCrawler:
    """Crawl QuantConnect documentation pages within a single /docs/v2/ section.

    Uses Playwright for JS-rendered HTML stability. Stays within the same
    section path — never follows links to external domains or other QC sections.
    """

    def __init__(self, delay: float = REQUEST_DELAY) -> None:
        self._delay = delay

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    async def fetch_page(self, url: str, page) -> Optional[str]:
        """Fetch a single page and return its raw HTML.

        Args:
            url: Full URL to fetch
            page: Playwright Page object

        Returns:
            Raw HTML string, or None on error
        """
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            await page.wait_for_timeout(500)  # allow JS to settle
            return await page.content()
        except Exception as exc:  # noqa: BLE001
            print(f"[crawler] Failed to fetch {url}: {exc}")
            return None

    async def crawl_section(
        self, section_key: str, base_path: str
    ) -> list[tuple[str, str]]:
        """Crawl all pages within a QC docs section.

        Args:
            section_key: Short identifier (used as raw/ subdirectory name)
            base_path: Section path relative to QC_DOCS_BASE

        Returns:
            List of (url, html) tuples for all crawled pages
        """
        # Import here to avoid hard dependency when Playwright isn't installed
        from playwright.async_api import async_playwright  # noqa: PLC0415

        # Support both full URLs (stored in URL_SECTIONS) and legacy relative paths
        if base_path.startswith("http"):
            section_url = base_path
        else:
            section_url = QC_DOCS_BASE.rstrip("/") + "/" + base_path.lstrip("/")
        queue = URLQueue(RAW_DIR / section_key / "_queue.json")
        queue.add(section_url)

        output_dir = RAW_DIR / section_key
        output_dir.mkdir(parents=True, exist_ok=True)

        results: list[tuple[str, str]] = []

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (compatible; LeanAlgoRAGBot/1.0)"
            )
            page = await context.new_page()

            page_count = 0
            for url in queue:
                if page_count >= MAX_PAGES_PER_SECTION:
                    print(f"[crawler] Reached page cap ({MAX_PAGES_PER_SECTION}) for {section_key}")
                    break

                html = await self.fetch_page(url, page)
                if html:
                    # Save raw HTML to disk
                    safe_name = self._url_to_filename(url)
                    (output_dir / safe_name).write_text(html, encoding="utf-8")

                    # Discover in-section links and enqueue them
                    for link in self._extract_section_links(html, url, base_path):
                        queue.add(link)

                    results.append((url, html))
                    page_count += 1

                time.sleep(self._delay)

            await browser.close()

        queue.save()
        print(f"[crawler] {section_key}: crawled {len(results)} pages")
        return results

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    def _extract_section_links(
        self, html: str, current_url: str, base_path: str
    ) -> list[str]:
        """Extract anchor href values that are within the same section path."""
        from bs4 import BeautifulSoup  # noqa: PLC0415

        soup = BeautifulSoup(html, "lxml")
        links = []
        # Support both full URLs (stored in URL_SECTIONS) and legacy relative paths
        if base_path.startswith("http"):
            section_prefix = base_path
        else:
            section_prefix = QC_DOCS_BASE.rstrip("/") + "/" + base_path.lstrip("/")

        for tag in soup.find_all("a", href=True):
            href = tag["href"]
            absolute = urljoin(current_url, href)
            # Strip fragment
            absolute = absolute.split("#")[0].rstrip("/")
            parsed = urlparse(absolute)
            if parsed.scheme not in ("http", "https"):
                continue
            # Only follow links within the same section
            if absolute.startswith(section_prefix):
                links.append(absolute)

        return list(set(links))

    @staticmethod
    def _url_to_filename(url: str) -> str:
        """Convert a URL to a safe filename for raw HTML storage."""
        path = urlparse(url).path.strip("/").replace("/", "_")
        return f"{path}.html" if path else "index.html"


def crawl_section_sync(section_key: str, base_path: str) -> list[tuple[str, str]]:
    """Synchronous wrapper around PlaywrightCrawler.crawl_section."""
    crawler = PlaywrightCrawler()
    return asyncio.run(crawler.crawl_section(section_key, base_path))
