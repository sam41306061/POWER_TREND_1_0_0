"""rag/processing/chunker.py — Split Markdown into header-aligned semantic chunks."""

import re
from typing import Any


class SemanticChunker:
    """Split a Markdown document into header-aligned chunks of 200–500 tokens.

    Each chunk corresponds to one H2 or H3 section. Code blocks are always kept
    with their surrounding explanation — never split mid-block.
    """

    # Approximate tokens per word (rough estimate; no tokenizer required)
    _WORDS_PER_TOKEN = 0.75
    _MIN_TOKENS = 50
    _MAX_TOKENS = 500
    _TARGET_TOKENS = 350

    def chunk_by_headers(self, markdown_text: str) -> list[dict[str, Any]]:
        """Split Markdown into chunks aligned to H2/H3 headers.

        Args:
            markdown_text: Full Markdown text of a documentation page

        Returns:
            List of dicts: {text, header_path, token_count}
        """
        sections = self._split_on_headers(markdown_text)
        chunks: list[dict[str, Any]] = []

        for header_path, body in sections:
            token_count = self._estimate_tokens(body)

            if token_count < self._MIN_TOKENS:
                # Too small — merge into previous chunk if possible
                if chunks:
                    prev = chunks[-1]
                    merged_text = prev["text"] + "\n\n" + body
                    prev["text"] = merged_text
                    prev["token_count"] = self._estimate_tokens(merged_text)
                continue

            if token_count <= self._MAX_TOKENS:
                chunks.append({
                    "text": body.strip(),
                    "header_path": header_path,
                    "token_count": token_count,
                })
            else:
                # Oversized — split at paragraph boundaries, keep code blocks intact
                sub_chunks = self._split_oversized(body, header_path)
                chunks.extend(sub_chunks)

        return chunks

    # -------------------------------------------------------------------------
    # Private
    # -------------------------------------------------------------------------

    _HEADER_RE = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)

    def _split_on_headers(self, text: str) -> list[tuple[list[str], str]]:
        """Return list of (header_path, body_text) for each H1/H2/H3 section."""
        matches = list(self._HEADER_RE.finditer(text))
        if not matches:
            return [([], text)]

        sections: list[tuple[list[str], str]] = []
        header_stack: list[tuple[int, str]] = []  # (level, title)

        for i, match in enumerate(matches):
            level = len(match.group(1))
            title = match.group(2).strip()

            # Pop headers at same or deeper level
            header_stack = [(lvl, t) for lvl, t in header_stack if lvl < level]
            header_stack.append((level, title))

            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            body = (match.group(0) + "\n" + text[start:end]).strip()

            path = [t for _, t in header_stack]
            sections.append((path, body))

        return sections

    def _split_oversized(
        self, text: str, header_path: list[str]
    ) -> list[dict[str, Any]]:
        """Split an oversized section at paragraph boundaries without breaking code blocks."""
        paragraphs = self._split_paragraphs_safe(text)
        chunks: list[dict[str, Any]] = []
        current_parts: list[str] = []
        current_tokens = 0

        for para in paragraphs:
            para_tokens = self._estimate_tokens(para)
            if current_tokens + para_tokens > self._TARGET_TOKENS and current_parts:
                body = "\n\n".join(current_parts)
                chunks.append({
                    "text": body.strip(),
                    "header_path": header_path,
                    "token_count": self._estimate_tokens(body),
                })
                current_parts = [para]
                current_tokens = para_tokens
            else:
                current_parts.append(para)
                current_tokens += para_tokens

        if current_parts:
            body = "\n\n".join(current_parts)
            chunks.append({
                "text": body.strip(),
                "header_path": header_path,
                "token_count": self._estimate_tokens(body),
            })

        return chunks

    def _split_paragraphs_safe(self, text: str) -> list[str]:
        """Split text into paragraphs, never breaking inside a code block."""
        parts: list[str] = []
        current: list[str] = []
        in_code = False

        for line in text.split("\n"):
            if line.startswith("```"):
                in_code = not in_code
                current.append(line)
            elif not in_code and line.strip() == "" and current:
                parts.append("\n".join(current))
                current = []
            else:
                current.append(line)

        if current:
            parts.append("\n".join(current))

        return [p for p in parts if p.strip()]

    def _estimate_tokens(self, text: str) -> int:
        """Rough token count estimate (words / 0.75)."""
        words = len(text.split())
        return max(1, int(words / self._WORDS_PER_TOKEN))
