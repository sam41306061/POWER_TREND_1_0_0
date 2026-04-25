"""rag/processing/markdown_converter.py — Convert cleaned HTML to Markdown."""

import re

import markdownify


class MarkdownConverter:
    """Convert cleaned HTML to Markdown, preserving code blocks and headers.

    Uses markdownify for the base conversion, then applies cleanup passes to
    remove excess whitespace while keeping code blocks intact.
    """

    def convert(self, html: str) -> str:
        """Convert HTML string to Markdown.

        Args:
            html: Cleaned HTML (output of HTMLCleaner.clean())

        Returns:
            Markdown string with code blocks and headers preserved
        """
        md = markdownify.markdownify(
            html,
            heading_style=markdownify.ATX,    # use # style headings
            code_language="python",
            strip=["img", "svg", "button"],
        )
        return self._cleanup(md)

    # -------------------------------------------------------------------------
    # Private
    # -------------------------------------------------------------------------

    def _cleanup(self, md: str) -> str:
        """Remove excess blank lines and trailing whitespace outside code blocks."""
        lines = md.split("\n")
        result = []
        in_code_block = False
        blank_streak = 0

        for line in lines:
            if line.startswith("```"):
                in_code_block = not in_code_block
                result.append(line)
                blank_streak = 0
                continue

            if in_code_block:
                result.append(line)
                continue

            stripped = line.rstrip()

            if stripped == "":
                blank_streak += 1
                if blank_streak <= 2:  # allow max 2 consecutive blank lines
                    result.append("")
            else:
                blank_streak = 0
                result.append(stripped)

        return "\n".join(result).strip()
