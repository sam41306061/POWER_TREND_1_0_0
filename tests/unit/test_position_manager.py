"""Unit tests for handlers.position_manager.PositionManager."""

from datetime import date

import config
from handlers.position_manager import PositionManager


def test_add_initial_leg(algo):
    pm = PositionManager(algo)
    trade = pm.add_leg("AAPL", fill_price=100.0, quantity=10, fill_date=date(2024, 1, 1))
    assert trade.leg_count == 1
    assert trade.total_quantity == 10
    assert trade.avg_entry_price == 100.0
    assert trade.entry_date == date(2024, 1, 1)
    assert pm.has_position_for_underlying("AAPL")


def test_add_multiple_legs_avg_cost(algo):
    pm = PositionManager(algo)
    pm.add_leg("AAPL", 100.0, 10, date(2024, 1, 1))
    pm.add_leg("AAPL", 110.0, 10, date(2024, 1, 5))
    trade = pm.get_trade("AAPL")
    assert trade.leg_count == 2
    assert trade.total_quantity == 20
    assert trade.avg_entry_price == 105.0
    assert trade.last_leg_date == date(2024, 1, 5)


def test_can_add_position_capacity(algo):
    pm = PositionManager(algo)
    for i in range(config.MAX_POSITIONS_OPEN):
        pm.add_leg(f"S{i}", 50.0, 1, date(2024, 1, 1))
    assert pm.can_add_position() is False


def test_close_trade_share_pnl(algo):
    pm = PositionManager(algo)
    pm.add_leg("X", 100.0, 10, date(2024, 1, 1))
    pm.add_leg("X", 110.0, 10, date(2024, 1, 5))
    algo.time = algo.time.replace(year=2024, month=1, day=20)
    result = pm.close_trade("X", exit_price=120.0, reason=config.EXIT_REASON_MANUAL)
    assert result is not None
    # avg = 105, qty = 20, pnl = (120 - 105) * 20 = 300
    assert result["pnl"] == 300.0
    assert result["total_quantity"] == 20
    assert "X" not in pm.active_trades


def test_close_unknown_trade_returns_none(algo):
    pm = PositionManager(algo)
    assert pm.close_trade("NOPE", 100.0, "X") is None
