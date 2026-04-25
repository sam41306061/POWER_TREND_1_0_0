"""
tests/unit/test_data_handler.py — Data Handler Tests
"""

from handlers.data_handler import DataHandler


class TestDataHandler:
    """Tests for DataHandler."""

    def test_data_handler__clear_cache__empties_cache(self, mock_algorithm):
        """clear_cache() should reset the internal cache."""
        handler = DataHandler(mock_algorithm)
        handler._cache[("AAPL", "2025-01-01")] = {"price": 150.0}
        handler.clear_cache()
        assert len(handler._cache) == 0

    def test_data_handler__get_indicators__returns_none_when_unimplemented(
        self, mock_algorithm
    ):
        """Stub implementation returns None (TODO for user)."""
        handler = DataHandler(mock_algorithm)
        result = handler.get_indicators("AAPL")
        assert result is None
