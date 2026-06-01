"""Multi-leg position lifecycle tests."""

from datetime import date

import config
from handlers.position_manager import PositionManager, TradeRecord


def test_open_position_creates_first_leg(mock_algorithm):
    pm = PositionManager(mock_algorithm)
    trade = pm.open_position("AAPL", fill_price=100.0, quantity=10,
                             entry_date=date(2024, 1, 5))

    assert trade.total_quantity == 10
    assert trade.leg_count == 1
    assert trade.avg_entry_price == 100.0
    assert pm.has_position("AAPL")


def test_add_leg_updates_avg_price(mock_algorithm):
    pm = PositionManager(mock_algorithm)
    pm.open_position("AAPL", 100.0, 10, date(2024, 1, 5))
    pm.add_leg("AAPL", 110.0, 10, date(2024, 1, 8))

    trade = pm.get("AAPL")
    assert trade.leg_count == 2
    assert trade.total_quantity == 20
    assert trade.avg_entry_price == 105.0


def test_pyramid_max_legs_enforced(mock_algorithm):
    pm = PositionManager(mock_algorithm)
    pm.open_position("AAPL", 100.0, 5, date(2024, 1, 1))
    for i in range(config.PYRAMID_MAX_ADDS):
        pm.add_leg("AAPL", 100.0 + i, 5, date(2024, 1, 2 + i))

    trade = pm.get("AAPL")
    assert trade.leg_count == 1 + config.PYRAMID_MAX_ADDS

    import pytest
    with pytest.raises(ValueError):
        pm.add_leg("AAPL", 120.0, 5, date(2024, 2, 1))


def test_reduce_position_realises_partial_pnl(mock_algorithm):
    pm = PositionManager(mock_algorithm)
    pm.open_position("AAPL", 100.0, 10, date(2024, 1, 1))
    pm.add_leg("AAPL", 110.0, 10, date(2024, 1, 2))

    result = pm.reduce_position("AAPL", sell_quantity=10, sell_price=120.0,
                                reason=config.EXIT_REASON_STRETCH_TRIM)
    assert result is not None
    # FIFO consumes the 100-leg first: (120-100)*10 = 200
    assert result["realized_pnl"] == 200.0
    trade = pm.get("AAPL")
    assert trade.total_quantity == 10
    assert trade.avg_entry_price == 110.0


def test_close_position_moves_to_closed_history(mock_algorithm):
    mock_algorithm.time = mock_algorithm.time.replace()
    pm = PositionManager(mock_algorithm)
    pm.open_position("AAPL", 100.0, 10, date(2024, 1, 1))
    summary = pm.close_position("AAPL", exit_price=120.0,
                                 reason=config.EXIT_REASON_SMA_BREAKDOWN)

    assert summary["pnl"] == 200.0
    assert not pm.has_position("AAPL")
    assert len(pm.closed_trades) == 1


def test_can_add_position_respects_max(mock_algorithm):
    pm = PositionManager(mock_algorithm)
    for i in range(config.MAX_POSITIONS_OPEN):
        pm.open_position(f"SYM{i}", 50.0, 1, date(2024, 1, 1))
    assert not pm.can_add_position()


class _FakeSymbol:
    """Mimic QC Symbol: ``.value`` is the ticker; identity differs each instance."""

    def __init__(self, ticker: str):
        self.value = ticker

    def __str__(self):
        return f"{self.value} R{id(self):X}"


def test_has_position_normalises_symbol_identity(mock_algorithm):
    """Regression: a fresh Symbol instance for the same ticker (e.g. after a
    universe refresh) must still resolve to the open position. Previously the
    dict was keyed on the Symbol object, causing daily re-entry spam."""
    pm = PositionManager(mock_algorithm)
    sym_a = _FakeSymbol("AAPL")
    pm.open_position(sym_a, 100.0, 10, date(2024, 1, 5))

    sym_b = _FakeSymbol("AAPL")  # different instance, same ticker
    assert sym_a is not sym_b
    assert pm.has_position(sym_b)
    assert pm.get(sym_b) is pm.get(sym_a)
