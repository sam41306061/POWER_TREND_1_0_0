"""Pyramiding sizing + add-on gating tests."""

from datetime import date

import config
from handlers.position_manager import PositionManager
from handlers.pyramiding_manager import PyramidingManager


def test_leg_quantity_uses_initial_leg_size_pct(mock_algorithm):
    mock_algorithm.portfolio.cash = 100_000.0
    pm = PyramidingManager(mock_algorithm)
    # 25% of $100k at $100 -> 250 shares
    qty = pm.leg_quantity(price=100.0)
    expected = int((100_000.0 * config.INITIAL_LEG_SIZE_PCT) / 100.0)
    assert qty == expected


def test_leg_quantity_zero_price_returns_zero(mock_algorithm):
    pm = PyramidingManager(mock_algorithm)
    assert pm.leg_quantity(0.0) == 0


def test_can_add_leg_blocks_same_bar(mock_algorithm, mock_indicators):
    positions = PositionManager(mock_algorithm)
    positions.open_position("AAPL", 100.0, 10, mock_algorithm.time.date())
    py = PyramidingManager(mock_algorithm)
    ok, reason = py.can_add_leg(positions.get("AAPL"), mock_indicators())
    assert not ok
    assert reason == "same_bar_as_last_leg"


def test_can_add_leg_blocks_max_legs(mock_algorithm, mock_indicators):
    positions = PositionManager(mock_algorithm)
    positions.open_position("AAPL", 100.0, 10, date(2024, 1, 1))
    for i in range(config.PYRAMID_MAX_ADDS):
        positions.add_leg("AAPL", 110.0, 10, date(2024, 1, 2 + i))
    py = PyramidingManager(mock_algorithm)
    ok, reason = py.can_add_leg(positions.get("AAPL"), mock_indicators())
    assert not ok
    assert reason == "max_legs"


def test_can_add_leg_requires_blue_bar(mock_algorithm, mock_indicators):
    positions = PositionManager(mock_algorithm)
    positions.open_position("AAPL", 100.0, 10, date(2024, 1, 1))
    py = PyramidingManager(mock_algorithm)
    ind = mock_indicators(is_blue_bar=False)
    ok, reason = py.can_add_leg(positions.get("AAPL"), ind)
    assert not ok
    assert reason == "not_blue_bar"


def test_can_add_leg_happy_path(mock_algorithm, mock_indicators):
    positions = PositionManager(mock_algorithm)
    positions.open_position("AAPL", 100.0, 10, date(2024, 1, 1))
    py = PyramidingManager(mock_algorithm)
    ok, reason = py.can_add_leg(positions.get("AAPL"), mock_indicators())
    assert ok
    assert reason == "ok"
