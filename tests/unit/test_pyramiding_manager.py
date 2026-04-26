"""Unit tests for handlers.pyramiding_manager.PyramidingManager."""

import math

import config
from handlers.pyramiding_manager import PyramidingManager


def test_size_leg_basic(algo):
    pm = PyramidingManager(algo)
    contracts = pm.size_leg(mid_premium=5.00, cash_value=100_000.0)
    # contracts = floor(0.05 * 100_000 / (5.00 * 100)) = floor(5000 / 500) = 10
    expected = math.floor(
        config.OPTION_PREMIUM_LEG_BUDGET_PCT
        * 100_000.0
        / (5.00 * config.OPTION_CONTRACT_MULTIPLIER)
    )
    assert contracts == expected


def test_size_leg_zero_when_invalid(algo):
    pm = PyramidingManager(algo)
    assert pm.size_leg(mid_premium=0.0, cash_value=100_000) == 0
    assert pm.size_leg(mid_premium=5.00, cash_value=0.0) == 0


def test_size_leg_rounds_down(algo):
    pm = PyramidingManager(algo)
    # budget = 0.05 * 10_000 = 500; cost per contract = 7.50 * 100 = 750 -> 0 contracts
    assert pm.size_leg(mid_premium=7.50, cash_value=10_000) == 0


def test_can_add_more_respects_cap(algo):
    pm = PyramidingManager(algo)
    assert pm.can_add_more(leg_count=0) is True
    assert pm.can_add_more(leg_count=config.PYRAMID_MAX_ADDS) is True  # initial + adds
    assert pm.can_add_more(leg_count=1 + config.PYRAMID_MAX_ADDS) is False
