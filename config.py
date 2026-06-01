"""
config.py — Single source of truth for Power Trend Algo 1 parameters.

All strategy thresholds are `Final`-typed constants. Never hardcode numeric
values in handlers — import from this module.

Spec: STRATEGY_OVERVIEW.md
"""

from typing import Final


# ==============================================================================
# REGIME (Power Trend on QQQ)
# ==============================================================================

REGIME_SYMBOL: Final[str] = "QQQ"
REGIME_EMA_PERIOD: Final[int] = 21
REGIME_SMA_PERIOD: Final[int] = 50

# Power Trend activation thresholds
LOW_ABOVE_EMA_DAYS: Final[int] = 10   # Rule 1
EMA_ABOVE_SMA_DAYS: Final[int] = 5    # Rule 2
SMA_SLOPE_LOOKBACK: Final[int] = 1    # Rule 3 lookback (today vs N days ago)

# Lite-mode toggles (Webster's personal relaxations)
REQUIRE_SMA50_RISING: Final[bool] = True       # Drop rule 3 if False
REQUIRE_ACTIVATION_UPDAY: Final[bool] = True   # Drop rule 4 if False
ENABLE_TREND_PRESSURE: Final[bool] = True      # Skip TREND_PRESSURE state if False


# ==============================================================================
# VOLATILITY
# ==============================================================================

ATR_PERIOD: Final[int] = 14                    # Stop-loss sizing
WEBBY_RSI_ATR_PERIOD: Final[int] = 50          # Webby RSI normalisation
WEBBY_RSI_STRETCH_LEVEL: Final[float] = 3.0    # Stretch-trim partial trigger


# ==============================================================================
# UNIVERSE
# ==============================================================================

UNIVERSE_TOP_N: Final[int] = 450               # Top-N by 20d avg dollar volume
UNIVERSE_REFRESH_DAYS: Final[int] = 14         # Refresh cadence (every 2 weeks)
MIN_PRICE: Final[float] = 20.0                 # Liquidity floor — price
MIN_DOLLAR_VOLUME: Final[float] = 50_000_000   # Liquidity floor — 20d avg $-vol
DOLLAR_VOLUME_LOOKBACK: Final[int] = 20


# ==============================================================================
# PER-STOCK INDICATORS
# ==============================================================================

STOCK_EMA_PERIOD: Final[int] = 21
STOCK_SMA_PERIOD: Final[int] = 50
STOCK_SMA10_PERIOD: Final[int] = 10


# ==============================================================================
# PYRAMIDING / SIZING
# ==============================================================================

PYRAMID_MAX_ADDS: Final[int] = 3               # Adds after the initial leg (so 4 legs max)
INITIAL_LEG_SIZE_PCT: Final[float] = 0.02      # Equal leg sizing (2% portfolio per leg) — per STRATEGY_OVERVIEW.md


# ==============================================================================
# RISK / EXITS
# ==============================================================================

MAX_POSITIONS_OPEN: Final[int] = 4             # Per STRATEGY_OVERVIEW.md
STOP_LOSS_PCT: Final[float] = 0.07             # 7% below avg_entry_price
MAX_ACCOUNT_DRAWDOWN_PCT: Final[float] = 0.15  # 15% account DD gate
PARTIAL_EXIT_TRIM_FRACTION: Final[float] = 0.50  # Stretch-trim sells 50%


# ==============================================================================
# SCHEDULING
# ==============================================================================

DAILY_EVAL_TIME: Final[str] = "09:35"


# ==============================================================================
# EXIT REASON CONSTANTS
# ==============================================================================

EXIT_REASON_STOP_LOSS: Final[str] = "STOP_LOSS"
EXIT_REASON_SMA_BREAKDOWN: Final[str] = "SMA_BREAKDOWN"
EXIT_REASON_EMA_CROSS: Final[str] = "EMA_CROSS"
EXIT_REASON_DRAWDOWN: Final[str] = "ACCOUNT_DRAWDOWN"
EXIT_REASON_STRETCH_TRIM: Final[str] = "STRETCH_TRIM"
EXIT_REASON_MANUAL: Final[str] = "MANUAL"
EXIT_REASON_ERROR: Final[str] = "ERROR"


# ==============================================================================
# REGIME STATE CONSTANTS
# ==============================================================================

REGIME_NO_TREND: Final[str] = "NO_TREND"
REGIME_TREND_UP: Final[str] = "TREND_UP"
REGIME_TREND_PRESSURE: Final[str] = "TREND_PRESSURE"
REGIME_TREND_END: Final[str] = "TREND_END"


# ==============================================================================
# VALIDATION
# ==============================================================================


def validate_config() -> None:
    """Sanity-check configuration on import."""
    assert LOW_ABOVE_EMA_DAYS > 0
    assert EMA_ABOVE_SMA_DAYS > 0
    assert REGIME_EMA_PERIOD < REGIME_SMA_PERIOD
    assert STOCK_EMA_PERIOD < STOCK_SMA_PERIOD
    assert UNIVERSE_TOP_N > 0
    assert UNIVERSE_REFRESH_DAYS > 0
    assert MIN_PRICE > 0
    assert MIN_DOLLAR_VOLUME > 0
    assert PYRAMID_MAX_ADDS >= 0
    assert 0.0 < INITIAL_LEG_SIZE_PCT <= 1.0
    assert INITIAL_LEG_SIZE_PCT * (1 + PYRAMID_MAX_ADDS) <= 1.0, (
        "Max position size (legs * leg_pct) exceeds 100% of portfolio"
    )
    assert 0.0 < STOP_LOSS_PCT < 1.0
    assert 0.0 < MAX_ACCOUNT_DRAWDOWN_PCT < 1.0
    assert 0.0 < PARTIAL_EXIT_TRIM_FRACTION <= 1.0
    assert WEBBY_RSI_STRETCH_LEVEL > 0
    assert MAX_POSITIONS_OPEN > 0
    # Aggregate exposure cap: every open position fully pyramided cannot exceed 100%
    # of portfolio. Without this, a misconfigured (size_pct, max_positions, max_adds)
    # tuple can demand impossible leverage and silently produce a broken backtest.
    assert (
        MAX_POSITIONS_OPEN * (1 + PYRAMID_MAX_ADDS) * INITIAL_LEG_SIZE_PCT <= 1.0
    ), (
        "Aggregate exposure (MAX_POSITIONS_OPEN * (1+PYRAMID_MAX_ADDS) * "
        "INITIAL_LEG_SIZE_PCT) exceeds 100% of portfolio"
    )


validate_config()
