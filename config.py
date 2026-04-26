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
# Per-leg sizing as a fraction of CURRENT CASH (not portfolio value).
# 5% of cash per leg keeps total deployed capital well under available cash even
# when MAX_POSITIONS_OPEN positions are stacked with full pyramid adds.
INITIAL_LEG_SIZE_PCT: Final[float] = 0.05


# ==============================================================================
# RISK / EXITS
# ==============================================================================

MAX_POSITIONS_OPEN: Final[int] = 10
# Deprecated: previously used as underlying-price stop for equities.
# The strategy now trades long calls; exits use OPTION_PREMIUM_STOP_LOSS_PCT instead.
STOP_LOSS_PCT: Final[float] = 0.07
MAX_ACCOUNT_DRAWDOWN_PCT: Final[float] = 0.15


# ==============================================================================
# OPTIONS (long-dated calls)
# ==============================================================================

# Days-to-expiry window for contract selection
OPTION_DTE_MIN: Final[int] = 90
OPTION_DTE_MAX: Final[int] = 270

# Delta band for selection. Lower bound 0.70 = deep ITM; upper 0.95 excludes
# effectively-delta-1 contracts that behave like the underlying.
OPTION_TARGET_DELTA: Final[float] = 0.70
OPTION_DELTA_MIN: Final[float] = 0.70
OPTION_DELTA_MAX: Final[float] = 0.95

# Force close any leg whose contract expires within this many calendar days.
OPTION_FORCE_EXIT_DAYS_BEFORE_EXPIRY: Final[int] = 14

# Liquidity / spread gates for selection
OPTION_MIN_OPEN_INTEREST: Final[int] = 100
OPTION_MAX_BID_ASK_SPREAD_PCT: Final[float] = 0.10  # (ask-bid)/mid

# Premium-loss stop per leg: exit a leg if current mid <= fill_premium * (1 - X)
OPTION_PREMIUM_STOP_LOSS_PCT: Final[float] = 0.50

# Per-leg premium budget as a fraction of CURRENT CASH
# (mirrors INITIAL_LEG_SIZE_PCT semantics, applied to option premium spend).
OPTION_PREMIUM_LEG_BUDGET_PCT: Final[float] = 0.05

# Standard listed equity option contract multiplier (shares per contract).
OPTION_CONTRACT_MULTIPLIER: Final[int] = 100


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
EXIT_REASON_PREMIUM_STOP: Final[str] = "PREMIUM_STOP_LOSS"
EXIT_REASON_DTE_FORCE: Final[str] = "DTE_FORCE_CLOSE"
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
    # Options
    assert 0 < OPTION_DTE_MIN < OPTION_DTE_MAX
    assert 0.0 < OPTION_DELTA_MIN <= OPTION_TARGET_DELTA <= OPTION_DELTA_MAX < 1.0
    assert 0 < OPTION_FORCE_EXIT_DAYS_BEFORE_EXPIRY < OPTION_DTE_MIN
    assert OPTION_MIN_OPEN_INTEREST >= 0
    assert 0.0 < OPTION_MAX_BID_ASK_SPREAD_PCT < 1.0
    assert 0.0 < OPTION_PREMIUM_STOP_LOSS_PCT < 1.0
    assert 0.0 < OPTION_PREMIUM_LEG_BUDGET_PCT <= 1.0
    assert OPTION_CONTRACT_MULTIPLIER > 0


validate_config()
