"""
config.py — Single source of truth for Power Trend Algo 1 parameters.

All strategy thresholds are Final-typed constants. Handlers must import
from this module; never hardcode numeric values in handlers.

See STRATEGY_OVERVIEW.md for the rationale behind each value.
"""

from typing import Final

# ==============================================================================
# REGIME (QQQ Power Trend state machine)
# ==============================================================================

REGIME_SYMBOL: Final[str] = "QQQ"
REGIME_EMA_PERIOD: Final[int] = 21
REGIME_SMA_PERIOD: Final[int] = 50
LOW_ABOVE_EMA_DAYS: Final[int] = 10  # Rule 1: days low > EMA21
EMA_ABOVE_SMA_DAYS: Final[int] = 5  # Rule 2: days EMA21 > SMA50
SMA_SLOPE_LOOKBACK: Final[int] = 1  # Rule 3: SMA50 rising vs N days ago

# Lite-mode toggles (Webster's personal relaxations). Strict defaults = all True.
REQUIRE_SMA50_RISING: Final[bool] = True
REQUIRE_ACTIVATION_UPDAY: Final[bool] = True
ENABLE_TREND_PRESSURE: Final[bool] = True

# ==============================================================================
# VOLATILITY (ATR + Webby RSI)
# ==============================================================================

ATR_PERIOD: Final[int] = 14  # Stop-loss sizing window
WEBBY_RSI_ATR_PERIOD: Final[int] = 50  # Webby RSI normalisation window
WEBBY_RSI_STRETCH_LEVEL: Final[float] = 3.0  # high_vs_sma10 trim trigger (ATRs)

# ==============================================================================
# UNIVERSE SELECTION (dynamic, no static CSV)
# ==============================================================================

UNIVERSE_TOP_N: Final[int] = 500  # Top N by 20d $-volume
UNIVERSE_REFRESH_DAYS: Final[int] = 14  # Re-rank every 2 weeks
MIN_PRICE: Final[float] = 20.0  # $/share floor
MIN_DOLLAR_VOLUME: Final[float] = 50_000_000  # 20d avg $-vol floor
DOLLAR_VOLUME_LOOKBACK: Final[int] = 20  # Days used for $-vol average

# ==============================================================================
# PER-STOCK INDICATORS
# ==============================================================================

STOCK_EMA_PERIOD: Final[int] = 21
STOCK_SMA_PERIOD: Final[int] = 50
STOCK_SMA10_PERIOD: Final[int] = 10  # For Webby RSI high_vs_sma10

# ==============================================================================
# ENTRY / PYRAMIDING
# ==============================================================================

PYRAMID_MAX_ADDS: Final[int] = 3  # Max ADDITIONAL legs on top of initial
INITIAL_LEG_SIZE_PCT: Final[float] = 0.02  # 2% of portfolio per leg

# ==============================================================================
# RISK / EXITS
# ==============================================================================

MAX_POSITIONS_OPEN: Final[int] = 4
STOP_LOSS_PCT: Final[float] = 0.07  # 7% from avg entry
TARGET_PROFIT_PCT: Final[float] = 0.75  # 75% from avg entry
MAX_ACCOUNT_DRAWDOWN_PCT: Final[float] = 0.15  # Suspend new entries beyond 15% DD
PARTIAL_EXIT_TRIM_FRACTION: Final[float] = 0.50  # 50% trim on stretch

# ==============================================================================
# SCHEDULING
# ==============================================================================

DAILY_EVAL_TIME: Final[str] = "09:35"  # Single daily callback after open

# ==============================================================================
# EXIT REASONS
# ==============================================================================

EXIT_REASON_DRAWDOWN: Final[str] = "ACCOUNT_DRAWDOWN"
EXIT_REASON_STOP_LOSS: Final[str] = "STOP_LOSS"
EXIT_REASON_TARGET_PROFIT: Final[str] = "TARGET_PROFIT"
EXIT_REASON_SMA_BREAKDOWN: Final[str] = "SMA_BREAKDOWN"
EXIT_REASON_EMA_CROSS: Final[str] = "EMA_CROSS"
EXIT_REASON_STRETCH_TRIM: Final[str] = "STRETCH_TRIM"

# ==============================================================================
# REGIME STATE LABELS
# ==============================================================================

REGIME_NO_TREND: Final[str] = "NO_TREND"
REGIME_TREND_UP: Final[str] = "TREND_UP"
REGIME_TREND_PRESSURE: Final[str] = "TREND_PRESSURE"
REGIME_TREND_END: Final[str] = "TREND_END"

# ==============================================================================
# VALIDATION
# ==============================================================================


def validate_config() -> None:
    """Validate config invariants."""
    assert LOW_ABOVE_EMA_DAYS > 0
    assert EMA_ABOVE_SMA_DAYS > 0
    assert REGIME_EMA_PERIOD < REGIME_SMA_PERIOD
    assert ATR_PERIOD > 0 and WEBBY_RSI_ATR_PERIOD > 0
    assert WEBBY_RSI_STRETCH_LEVEL > 0
    assert UNIVERSE_TOP_N > 0
    assert UNIVERSE_REFRESH_DAYS > 0
    assert MIN_PRICE > 0 and MIN_DOLLAR_VOLUME > 0
    assert DOLLAR_VOLUME_LOOKBACK > 0
    assert PYRAMID_MAX_ADDS >= 0
    assert 0.0 < INITIAL_LEG_SIZE_PCT < 1.0
    assert MAX_POSITIONS_OPEN > 0
    assert 0.0 < STOP_LOSS_PCT < 1.0
    assert TARGET_PROFIT_PCT > 0
    assert 0.0 < MAX_ACCOUNT_DRAWDOWN_PCT < 1.0
    assert 0.0 < PARTIAL_EXIT_TRIM_FRACTION <= 1.0


validate_config()
