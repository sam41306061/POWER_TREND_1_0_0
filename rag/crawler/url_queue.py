"""rag/crawler/url_queue.py — URL queue for tracking crawl progress."""

import json
from pathlib import Path
from typing import Iterator, Optional


class URLQueue:
    """Track visited and unvisited URLs for a single crawl session.

    State is persisted to a JSON file so interrupted crawls can resume.
    """

    def __init__(self, queue_path: Path) -> None:
        self._path = queue_path
        self._visited: set[str] = set()
        self._pending: list[str] = []

    # -------------------------------------------------------------------------
    # Seeding
    # -------------------------------------------------------------------------

    def seed_from_sections(self, sections: dict[str, str], base_url: str) -> None:
        """Populate the queue from the URL_SECTIONS config dict.

        Args:
            sections: mapping of section_key -> relative_path
            base_url: QC_DOCS_BASE prefix (e.g. "https://www.quantconnect.com/docs/v2")
        """
        for path in sections.values():
            url = base_url.rstrip("/") + "/" + path.lstrip("/")
            self.add(url)

    def add(self, url: str) -> None:
        """Add a URL to the pending queue if not already seen."""
        if url not in self._visited and url not in self._pending:
            self._pending.append(url)

    # -------------------------------------------------------------------------
    # Iteration
    # -------------------------------------------------------------------------

    def pop(self) -> Optional[str]:
        """Return and remove the next unvisited URL, or None if queue is empty."""
        if not self._pending:
            return None
        url = self._pending.pop(0)
        self._visited.add(url)
        return url

    def __iter__(self) -> Iterator[str]:
        """Drain the queue, marking each URL visited as it is yielded."""
        while self._pending:
            yield self.pop()

    def __len__(self) -> int:
        return len(self._pending)

    @property
    def visited_count(self) -> int:
        return len(self._visited)

    # -------------------------------------------------------------------------
    # Persistence
    # -------------------------------------------------------------------------

    def save(self) -> None:
        """Persist queue state to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        state = {
            "visited": list(self._visited),
            "pending": self._pending,
        }
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)

    def load(self) -> None:
        """Restore queue state from disk. No-op if file does not exist."""
        if not self._path.exists():
            return
        with open(self._path, encoding="utf-8") as f:
            state = json.load(f)
        self._visited = set(state.get("visited", []))
        self._pending = state.get("pending", [])
