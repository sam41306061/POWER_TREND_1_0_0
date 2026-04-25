"""
handlers/universe_filter.py — Static Universe Selection

Responsibility:
  Load a candidate symbol list from CSV and return it as a set of ticker strings.

Contract:
  get_universe() → list[str]   Ticker strings (e.g., ["AAPL", "MSFT", ...])
"""

import csv
from pathlib import Path

import config


class UniverseFilter:
    """Load and cache the static universe from CSV."""

    def __init__(self, algorithm):
        self._algo = algorithm
        self._universe: list[str] = []
        self._load_universe()

    def _load_universe(self) -> None:
        """Load symbols from the configured CSV file."""
        csv_path = Path(config.UNIVERSE_CSV_PATH)
        if not csv_path.exists():
            self._algo.debug(f"[UNIVERSE] CSV not found: {csv_path}")
            return

        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            self._universe = [
                row["symbol"].strip().upper()
                for row in reader
                if row.get("symbol", "").strip()
            ]

        self._algo.debug(f"[UNIVERSE] Loaded {len(self._universe)} symbols from {csv_path}")

    def get_universe(self) -> list[str]:
        """Return the full list of candidate ticker strings."""
        return self._universe
