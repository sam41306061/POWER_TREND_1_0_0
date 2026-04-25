"""rag/processing/html_cleaner.py — Strip non-content HTML from QC docs pages."""

from typing import Optional

from bs4 import BeautifulSoup, Tag


class HTMLCleaner:
    """Extract the main content from a QC docs HTML page.

    Removes navigation, sidebars, ads, scripts, and other boilerplate.
    Returns a cleaned HTML string suitable for Markdown conversion.
    """

    # CSS selectors for elements to remove before extraction
    _REMOVE_SELECTORS = [
        "nav",
        "header",
        "footer",
        "[class*='sidebar']",
        "[class*='nav']",
        "[class*='menu']",
        "[class*='breadcrumb']",
        "[class*='toc']",
        "[class*='table-of-contents']",
        # NOTE: [class*='ad'] intentionally omitted — too broad; matches 'heading',
        # 'loaded', 'reading', 'shadow' etc. and destroys QC doc content sections.
        "[class='ad']",
        "[class*='advertisement']",
        "[class*='banner']",
        "[class*='cookie']",
        "script",
        "style",
        "noscript",
        "iframe",
    ]

    # Candidate selectors for the main content area (tried in order)
    # QC-specific selectors first, then generic fallbacks
    _MAIN_CONTENT_SELECTORS = [
        ".article-body",            # QC docs primary content div
        ".section-container",       # QC docs section wrapper
        "article",
        "main",
        "[class*='content']",
        "[class*='documentation']",
        "[class*='docs-content']",
        "[role='main']",
        "#content",
        "#main",
    ]

    def clean(self, html: str) -> str:
        """Return cleaned HTML containing only the main documentation content.

        Args:
            html: Raw HTML from the crawler

        Returns:
            Cleaned HTML string (may be empty string if no content found)
        """
        soup = BeautifulSoup(html, "lxml")
        self.remove_nav(soup)
        self.remove_scripts(soup)
        main = self.extract_main_content(soup)
        if main is None:
            return ""
        return str(main)

    def remove_nav(self, soup: BeautifulSoup) -> None:
        """Remove navigation and sidebar elements in-place."""
        for selector in self._REMOVE_SELECTORS[:8]:  # nav/menu/sidebar selectors
            for element in soup.select(selector):
                element.decompose()

    def remove_scripts(self, soup: BeautifulSoup) -> None:
        """Remove scripts, styles, and other non-text elements in-place."""
        for selector in self._REMOVE_SELECTORS[8:]:  # script/style/noscript etc.
            for element in soup.select(selector):
                element.decompose()

    def remove_ads(self, soup: BeautifulSoup) -> None:
        """Remove ad and banner elements in-place."""
        for selector in ["[class*='ad']", "[class*='banner']", "[class*='cookie']"]:
            for element in soup.select(selector):
                element.decompose()

    def extract_main_content(self, soup: BeautifulSoup) -> Optional[Tag]:
        """Find and return the main content Tag.

        Tries each selector in _MAIN_CONTENT_SELECTORS in order.
        Falls back to <body> if none match.
        """
        for selector in self._MAIN_CONTENT_SELECTORS:
            result = soup.select_one(selector)
            if result and len(result.get_text(strip=True)) > 100:
                return result
        # Fallback: whole body
        return soup.find("body")
