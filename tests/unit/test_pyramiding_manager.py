"""tests/unit/test_pyramiding_manager.py — Leg sizing and pyramid cap."""

from math import floor
from dataclasses import dataclass

import config
from handlers.pyramiding_manager import PyramidingManager


@dataclass
class _MockTrade:
    leg_count: int = 1


class TestLegSize:
    def test_floor_math(self, mock_algorithm):
        pm = PyramidingManager(mock_algorithm)
        pv = 100_000.0
        price = 73.0
        expected = floor(config.INITIAL_LEG_SIZE_PCT * pv / price)
        assert pm.compute_leg_size(pv, price) == expected

    def test_zero_portfolio_returns_zero(self, mock_algorithm):
        pm = PyramidingManager(mock_algorithm)
        assert pm.compute_leg_size(0, 100) == 0

    def test_zero_price_returns_zero(self, mock_algorithm):
        pm = PyramidingManager(mock_algorithm)
        assert pm.compute_leg_size(100_000, 0) == 0


class TestCanAdd:
    def test_room_to_add(self, mock_algorithm):
        pm = PyramidingManager(mock_algorithm)
        trade = _MockTrade(leg_count=1)
        assert pm.can_add(trade) is True

    def test_at_cap_blocks(self, mock_algorithm):
        pm = PyramidingManager(mock_algorithm)
        trade = _MockTrade(leg_count=1 + config.PYRAMID_MAX_ADDS)
        assert pm.can_add(trade) is False

    def test_none_trade_returns_false(self, mock_algorithm):
        pm = PyramidingManager(mock_algorithm)
        assert pm.can_add(None) is False
