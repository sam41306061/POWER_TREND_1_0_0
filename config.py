"""
config.py — Single source of truth for all Power Trend Algo 1 parameters.

All strategy thresholds belong here as Final-typed constants.
Never hardcode numeric values in handlers — import from this module.

Spec: docs/STRATEGY_OVERVIEW.md
"""

from typing import Final


# ==============================================================================
# REGIME (QQQ Power Trend gate)
# ==============================================================================

REGIME_SYMBOL: Final[str] = "QQQ"
REGIME_EMA_PERIOD: Final[int] = 21
REGIME_SMA_PERIOD: Final[int] = 50
LOW_ABOVE_EMA_DAYS: Final[int] = 10
EMA_ABOVE_SMA_DAYS: Final[int] = 5
SMA_SLOPE_LOOKBACK: Final[int] = 1

# Lite-mode toggles (Webster's personal relaxations)
REQUIRE_SMA50_RISING: Final[bool] = True
REQUIRE_ACTIVATION_UPDAY: Final[bool] = True
ENABLE_TREND_PRESSURE: Final[bool] = True


# ==============================================================================
# VOLATILITY
# ==============================================================================

ATR_PERIOD: Final[int] = 14


# ==============================================================================
# UNIVERSE
# ==============================================================================

UNIVERSE_TOP_N: Final[int] = 200
UNIVERSE_REFRESH_DAYS: Final[int] = 14
MIN_PRICE: Final[float] = 20.0
MIN_DOLLAR_VOLUME: Final[float] = 50_000_000
DOLLAR_VOLUME_LOOKBACK: Final[int] = 20


# ==============================================================================
# ENTRY / PYRAMIDING
# ==============================================================================

STOCK_EMA_PERIOD: Final[int] = 21
STOCK_SMA_PERIOD: Final[int] = 50
PYRAMID_MAX_ADDS: Final[int] = 3
INITIAL_LEG_SIZE_PCT: Final[float] = 0.25


# ==============================================================================
# RISK / EXITS
# ==============================================================================

MAX_POSITIONS_OPEN: Final[int] = 10
STOP_LOSS_PCT: Final[float] = 0.07
MAX_ACCOUNT_DRAWDOWN_PCT: Final[float] = 0.15


# ==============================================================================
# SCHEDULING
# ==============================================================================

DAILY_EVAL_TIME: Final[str] = "09:35"


# ==============================================================================
# REGIME STATES
# ==============================================================================

REGIME_NO_TREND: Final[str] = "NO_TREND"
REGIME_TREND_UP: Final[str] = "TREND_UP"
REGIME_TREND_PRESSURE: Final[str] = "TREND_PRESSURE"
REGIME_TREND_END: Final[str] = "TREND_END"


# ==============================================================================
# EXIT REASONS
# ==============================================================================

EXIT_REASON_DRAWDOWN: Final[str] = "ACCOUNT_DRAWDOWN"
EXIT_REASON_STOP_LOSS: Final[str] = "STOP_LOSS"
EXIT_REASON_SMA_BREAKDOWN: Final[str] = "SMA_BREAKDOWN"
EXIT_REASON_EMA_CROSS: Final[str] = "EMA_CROSS"
EXIT_REASON_MANUAL: Final[str] = "MANUAL"


# ==============================================================================
# VALIDATION
# ==============================================================================


def validate_config() -> None:
    assert REGIME_EMA_PERIOD < REGIME_SMA_PERIOD
    assert LOW_ABOVE_EMA_DAYS > 0 and EMA_ABOVE_SMA_DAYS > 0
    assert UNIVERSE_TOP_N > 0
    assert MIN_PRICE > 0 and MIN_DOLLAR_VOLUME > 0
    assert 0.0 < INITIAL_LEG_SIZE_PCT <= 1.0
    assert PYRAMID_MAX_ADDS >= 0
    assert MAX_POSITIONS_OPEN > 0
    assert 0.0 < STOP_LOSS_PCT < 1.0
    assert 0.0 < MAX_ACCOUNT_DRAWDOWN_PCT < 1.0


validate_config()
