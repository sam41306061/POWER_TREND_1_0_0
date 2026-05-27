"""tests/unit/test_position_manager.py — Multi-leg avg-cost position book."""

from datetime import date

import config
from handlers.position_manager import PositionManager


class TestAddLeg:
    def test_first_leg_creates_trade(self, mock_algorithm):
        pm = PositionManager(mock_algorithm)
        trade = pm.add_leg("AAPL", 100.0, 10, date(2025, 1, 15))
        assert pm.has_position("AAPL")
        assert trade.total_quantity == 10
        assert trade.avg_entry_price == 100.0
        assert trade.leg_count == 1
        assert trade.last_leg_date == date(2025, 1, 15)

    def test_second_leg_updates_avg_cost(self, mock_algorithm):
        pm = PositionManager(mock_algorithm)
        pm.add_leg("AAPL", 100.0, 10, date(2025, 1, 15))
        trade = pm.add_leg("AAPL", 110.0, 10, date(2025, 1, 22))
        assert trade.total_quantity == 20
        assert trade.avg_entry_price == 105.0  # (100*10 + 110*10) / 20
        assert trade.leg_count == 2
        assert trade.last_leg_date == date(2025, 1, 22)

    def test_three_legs_weighted_average(self, mock_algorithm):
        pm = PositionManager(mock_algorithm)
        pm.add_leg("AAPL", 100.0, 10, date(2025, 1, 1))
        pm.add_leg("AAPL", 120.0, 5, date(2025, 1, 8))
        trade = pm.add_leg("AAPL", 130.0, 5, date(2025, 1, 15))
        expected = (100 * 10 + 120 * 5 + 130 * 5) / 20
        assert trade.total_quantity == 20
        assert abs(trade.avg_entry_price - expected) < 1e-9


class TestReducePosition:
    def test_partial_reduce_preserves_avg_cost(self, mock_algorithm):
        pm = PositionManager(mock_algorithm)
        pm.add_leg("AAPL", 100.0, 10, date(2025, 1, 1))
        pm.add_leg("AAPL", 110.0, 10, date(2025, 1, 8))
        result = pm.reduce_position("AAPL", 10, 120.0, "STRETCH_TRIM")
        trade = pm.get_trade("AAPL")
        assert result["sold_quantity"] == 10
        assert trade.total_quantity == 10
        assert abs(trade.avg_entry_price - 105.0) < 1e-9

    def test_full_reduce_promotes_to_closed(self, mock_algorithm):
        pm = PositionManager(mock_algorithm)
        pm.add_leg("AAPL", 100.0, 10, date(2025, 1, 1))
        pm.reduce_position("AAPL", 10, 120.0, "STRETCH_TRIM")
        assert not pm.has_position("AAPL")

    def test_returns_none_when_no_position(self, mock_algorithm):
        pm = PositionManager(mock_algorithm)
        assert pm.reduce_position("AAPL", 5, 100.0, "X") is None


class TestCloseTrade:
    def test_close_returns_pnl(self, mock_algorithm):
        pm = PositionManager(mock_algorithm)
        pm.add_leg("AAPL", 100.0, 10, date(2025, 1, 1))
        out = pm.close_trade("AAPL", 120.0, "TARGET_PROFIT")
        assert out["quantity"] == 10
        assert out["pnl"] == (120.0 - 100.0) * 10
        assert not pm.has_position("AAPL")

    def test_close_unknown_returns_none(self, mock_algorithm):
        pm = PositionManager(mock_algorithm)
        assert pm.close_trade("MSFT", 100.0, "X") is None


class TestCapacity:
    def test_can_add_position_under_limit(self, mock_algorithm):
        pm = PositionManager(mock_algorithm)
        assert pm.can_add_position() is True

    def test_can_add_position_at_limit(self, mock_algorithm):
        pm = PositionManager(mock_algorithm)
        for i in range(config.MAX_POSITIONS_OPEN):
            pm.add_leg(f"S{i}", 100.0, 1, date(2025, 1, 1))
        assert pm.can_add_position() is False
