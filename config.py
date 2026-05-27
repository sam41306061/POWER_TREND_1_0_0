"""
config.py — Single source of truth for all strategy parameters.

All strategy thresholds belong here as Final-typed constants.
Never hardcode numeric values in handlers — import from this module.

TODO: Replace all placeholder values with your strategy's parameters.
"""

from typing import Final, List

# ==============================================================================
# UNIVERSE SELECTION
# ==============================================================================

# Path to static candidate list (CSV with a 'symbol' column)
UNIVERSE_CSV_PATH: Final[str] = "universe/candidates.csv"

# Dynamic filtering thresholds (used when universe is filtered programmatically)
MIN_MARKET_CAP: Final[float] = 10_000_000_000  # $10B minimum market cap
MIN_AVG_VOLUME: Final[int] = 1_000_000  # Minimum 1M average daily volume
UNIVERSE_TOP_N: Final[int] = 450  # Top-N stocks by 20d avg dollar volume (see STRATEGY_OVERVIEW.md)

# ==============================================================================
# EVENT TIMING
#
# Define the event window your strategy trades around.
# Examples:
#   - Event-based: 7–30 days before target event
#   - Dividends: 5–20 days before ex-dividend date
#   - Macro: 1–5 days before FOMC announcement
#   - Technical: N/A (set to large window or remove)
# ==============================================================================

MIN_DAYS_TO_EVENT: Final[int] = 7  # Minimum days before target event
MAX_DAYS_TO_EVENT: Final[int] = 30  # Maximum days before target event

# ==============================================================================
# INDICATOR PERIODS
#
# Define the technical indicator periods your strategy uses.
# Add or remove indicators as needed.
# ==============================================================================

SMA_LONG_PERIOD: Final[int] = 50  # Long-term simple moving average
EMA_SHORT_PERIOD: Final[int] = 8  # Short-term exponential moving average
EMA_MID_PERIOD: Final[int] = 21  # Medium-term exponential moving average
EMA_LONG_PERIOD: Final[int] = 34  # Long-term exponential moving average
ATR_PERIOD: Final[int] = 14  # Average true range period

# ==============================================================================
# ENTRY CRITERIA
#
# Define the gates/filters that must pass before entering a position.
# ==============================================================================

PRICE_ABOVE_SMA_REQUIRED: Final[bool] = True  # Require price above long SMA
MAX_ATR_EXTENSION: Final[float] = 2.0  # Max ATR multiple above mean (avoid chasing)
ENTRY_ZONE_EMAS: Final[List[int]] = [8, 21, 34]  # EMAs defining the entry zone
ENTRY_ZONE_TOLERANCE_PCT: Final[float] = 2.0  # Max % distance from entry EMA

# ==============================================================================
# MARKET REGIME
#
# Define the broad market filter (e.g., SPY trend check).
# ==============================================================================

MARKET_REGIME_EMA: Final[int] = 21  # EMA period for regime filter
MARKET_REGIME_SMA: Final[int] = 50  # SMA period for regime filter
RESTRICT_TRADES_IN_DOWNTREND: Final[bool] = True  # Only trade in uptrend

# ==============================================================================
# OPTIONS SELECTION (if trading options — otherwise remove this section)
# ==============================================================================

TARGET_DELTA: Final[float] = 0.30  # Target delta for option selection
DELTA_TOLERANCE: Final[float] = 0.05  # Acceptable deviation from target delta
MIN_OPEN_INTEREST_MULTIPLIER: Final[int] = 100  # Min OI = multiplier * contracts

# IV analytics
IV_ELEVATED_THRESHOLD_PCT: Final[float] = 150.0  # IV elevated if >= 150% of rolling avg
IV_ROLLING_AVG_DAYS: Final[int] = 30  # Rolling IV average window (trading days)

# Options math
TRADING_DAYS_PER_YEAR: Final[int] = 252

# ==============================================================================
# POSITION SIZING
# ==============================================================================

MAX_POSITIONS_OPEN: Final[int] = 10  # Maximum concurrent positions
FIXED_CONTRACTS: Final[int] = 10  # Fixed number of contracts per position
POSITION_RISK_PCT: Final[float] = 0.02  # Risk 2% of portfolio per position

# ==============================================================================
# EXIT RULES
#
# Define your exit conditions. Adapt to your strategy:
#   - Stop loss levels
#   - Profit targets
#   - Time-based exits
#   - Event-proximity exits
# ==============================================================================

STOP_LOSS_PCT: Final[float] = 0.50  # 50% stop loss
PROFIT_TARGET_PCT: Final[float] = 1.00  # 100% profit target (disable with large value)
MAX_HOLDING_DAYS: Final[int] = 30  # Maximum days to hold a position

# ==============================================================================
# TIMING & SCHEDULING
# ==============================================================================

SCAN_SCHEDULE_TIME: Final[str] = "09:35"  # Daily universe scan time
ENTRY_TRIGGER_TIME: Final[str] = "10:00"  # Entry signal check time
EXIT_CHECK_TIMES: Final[List[str]] = ["10:00", "14:00", "15:30"]  # Intraday exit checks

# ==============================================================================
# NAMED CONSTANTS — EXIT REASONS
# ==============================================================================

EXIT_REASON_STOP_LOSS: Final[str] = "STOP_LOSS"
EXIT_REASON_PROFIT_TARGET: Final[str] = "PROFIT_TARGET"
EXIT_REASON_TIME_LIMIT: Final[str] = "TIME_LIMIT"
EXIT_REASON_EVENT_PROXIMITY: Final[str] = "EVENT_PROXIMITY"
EXIT_REASON_MANUAL: Final[str] = "MANUAL"
EXIT_REASON_ERROR: Final[str] = "ERROR"

# ==============================================================================
# NAMED CONSTANTS — MARKET REGIME
# ==============================================================================

MARKET_REGIME_UPTREND: Final[str] = "UPTREND"
MARKET_REGIME_DOWNTREND: Final[str] = "DOWNTREND"
MARKET_REGIME_NEUTRAL: Final[str] = "NEUTRAL"
MARKET_REGIME_UNKNOWN: Final[str] = "UNKNOWN"

# ==============================================================================
# VALIDATION
# ==============================================================================


def validate_config() -> None:
    """Validate configuration parameters for logical consistency."""
    assert MIN_DAYS_TO_EVENT < MAX_DAYS_TO_EVENT, (
        "MIN_DAYS_TO_EVENT must be less than MAX_DAYS_TO_EVENT"
    )

    assert 0.0 < TARGET_DELTA < 1.0, "TARGET_DELTA must be between 0.0 and 1.0"

    assert MAX_POSITIONS_OPEN > 0, "MAX_POSITIONS_OPEN must be positive"

    assert FIXED_CONTRACTS > 0, "FIXED_CONTRACTS must be positive"

    assert 0.0 < POSITION_RISK_PCT < 1.0, (
        "POSITION_RISK_PCT must be between 0.0 and 1.0"
    )

    assert len(ENTRY_ZONE_EMAS) > 0, "ENTRY_ZONE_EMAS must contain at least one period"

    assert all(period > 0 for period in ENTRY_ZONE_EMAS), (
        "All ENTRY_ZONE_EMAS periods must be positive"
    )


# Run validation on import
validate_config()
