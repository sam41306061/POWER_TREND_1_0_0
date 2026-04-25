"""
tests/unit/test_position_manager.py — Position Manager Tests
"""

from datetime import date

from handlers.position_manager import PositionManager, TradeRecord


class TestPositionManager:
    """Tests for PositionManager."""

    def test_position_manager__can_add_position__under_limit(self, mock_algorithm):
        """can_add_position() returns True when under MAX_POSITIONS_OPEN."""
        pm = PositionManager(mock_algorithm)
        assert pm.can_add_position() is True

    def test_position_manager__add_trade__tracks_position(self, mock_algorithm):
        """add_trade() creates a TradeRecord in active_trades."""
        pm = PositionManager(mock_algorithm)
        trade = pm.add_trade(
            symbol="AAPL",
            instrument_symbol="AAPL_C_150",
            fill_price=5.0,
            quantity=10,
            trade_type="SETUP",
            entry_date=date(2025, 1, 15),
            target_delta=0.30,
        )
        assert "AAPL_C_150" in pm.active_trades
        assert trade.entry_price == 5.0
        assert trade.status == "OPEN"

    def test_position_manager__close_trade__returns_pnl(self, mock_algorithm):
        """close_trade() returns summary dict with P&L."""
        pm = PositionManager(mock_algorithm)
        pm.add_trade(
            symbol="AAPL",
            instrument_symbol="AAPL_C_150",
            fill_price=5.0,
            quantity=10,
            trade_type="SETUP",
            entry_date=date(2025, 1, 15),
        )
        result = pm.close_trade("AAPL_C_150", exit_price=7.0, reason="PROFIT_TARGET")
        assert result is not None
        assert result["pnl"] == (7.0 - 5.0) * 10 * 100
        assert "AAPL_C_150" not in pm.active_trades

    def test_position_manager__has_position_for_underlying__detects_duplicate(
        self, mock_algorithm
    ):
        """has_position_for_underlying() returns True if position exists."""
        pm = PositionManager(mock_algorithm)
        pm.add_trade(
            symbol="AAPL",
            instrument_symbol="AAPL_C_150",
            fill_price=5.0,
            quantity=10,
            trade_type="SETUP",
            entry_date=date(2025, 1, 15),
        )
        assert pm.has_position_for_underlying("AAPL") is True
        assert pm.has_position_for_underlying("MSFT") is False
