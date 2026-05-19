"""Unit tests for handlers.pyramiding_manager.PyramidingManager."""

import math

import config
from handlers.pyramiding_manager import PyramidingManager


def test_size_leg_basic(algo):
    pm = PyramidingManager(algo)
    qty = pm.size_leg(price=100.0, portfolio_value=100_000.0)
    expected = math.floor(config.INITIAL_LEG_SIZE_PCT * 100_000.0 / 100.0)
    assert qty == expected


def test_size_leg_zero_when_invalid(algo):
    pm = PyramidingManager(algo)
    assert pm.size_leg(price=0.0, portfolio_value=100_000) == 0
    assert pm.size_leg(price=100, portfolio_value=0.0) == 0


def test_can_add_more_respects_cap(algo):
    pm = PyramidingManager(algo)
    assert pm.can_add_more(leg_count=0) is True
    assert pm.can_add_more(leg_count=config.PYRAMID_MAX_ADDS) is True  # initial + adds
    assert pm.can_add_more(leg_count=1 + config.PYRAMID_MAX_ADDS) is False
