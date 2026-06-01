"""Smoke test that config constants are self-consistent."""

import importlib
from unittest import mock

import pytest

import config


def test_validate_config_passes():
    config.validate_config()  # raises AssertionError on failure


def test_max_legs_does_not_exceed_portfolio():
    total = config.INITIAL_LEG_SIZE_PCT * (1 + config.PYRAMID_MAX_ADDS)
    assert total <= 1.0


def test_aggregate_exposure_invariant_fires():
    """Regression: silently shipping a (size_pct, max_positions, max_adds) tuple
    that demands >100% portfolio exposure caused the first backtest to spam
    'Insufficient buying power' errors. validate_config() must reject it."""
    with mock.patch.object(config, "MAX_POSITIONS_OPEN", 10), \
         mock.patch.object(config, "INITIAL_LEG_SIZE_PCT", 0.25), \
         mock.patch.object(config, "PYRAMID_MAX_ADDS", 3):
        with pytest.raises(AssertionError, match="[Aa]ggregate exposure"):
            config.validate_config()


def test_regime_state_constants_unique():
    states = {
        config.REGIME_NO_TREND,
        config.REGIME_TREND_UP,
        config.REGIME_TREND_PRESSURE,
        config.REGIME_TREND_END,
    }
    assert len(states) == 4
