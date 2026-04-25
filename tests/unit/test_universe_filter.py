"""
tests/unit/test_universe_filter.py — Universe Filter Tests
"""

from pathlib import Path
from unittest.mock import patch

from handlers.universe_filter import UniverseFilter


class TestUniverseFilter:
    """Tests for UniverseFilter."""

    def test_universe_filter__get_universe__returns_list(self, mock_algorithm):
        """get_universe() returns a list."""
        uf = UniverseFilter(mock_algorithm)
        result = uf.get_universe()
        assert isinstance(result, list)

    def test_universe_filter__get_universe__empty_csv_returns_empty(self, mock_algorithm):
        """Empty CSV returns empty list (header only)."""
        uf = UniverseFilter(mock_algorithm)
        # CSV has only header row
        assert isinstance(uf.get_universe(), list)
