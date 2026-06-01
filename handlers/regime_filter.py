"""
handlers/regime_filter.py — Power Trend Regime State Machine

Tracks the QQQ Power Trend state daily. Entries are only permitted while
the regime is `TREND_UP` (or `TREND_PRESSURE` if enabled — see config).

Power Trend ACTIVATION (NO_TREND → TREND_UP) requires all of:
    1. QQQ low has stayed above EMA21 for >= LOW_ABOVE_EMA_DAYS
    2. EMA21 has been above SMA50 for >= EMA_ABOVE_SMA_DAYS
    3. SMA50 today > SMA50 SMA_SLOPE_LOOKBACK days ago    (toggle)
    4. Activation day is an up-day (close > prior_close)  (toggle)

Power Trend DEACTIVATION (any state → TREND_END):
    EMA21 closes below SMA50.

TREND_PRESSURE (optional intermediate state):
    Enter TREND_PRESSURE when QQQ low closes below EMA21 while in TREND_UP.
    Exit TREND_PRESSURE back to TREND_UP when low re-reclaims EMA21.
    Entries continue to be allowed in TREND_PRESSURE.
"""

from __future__ import annotations

import config


class RegimeFilter:
    """Daily QQQ Power Trend classifier."""

    def __init__(self, algorithm):
        self._algo = algorithm
        # Streak counters
        self._days_low_above_ema21: int = 0
        self._days_ema21_above_sma50: int = 0
        # Current state
        self._state: str = config.REGIME_NO_TREND

    # ------------------------------------------------------------------
    # Daily update
    # ------------------------------------------------------------------
    def update(self, indicators: dict | None) -> str:
        """
        Advance state given today's QQQ indicators.

        Args:
            indicators: dict returned by DataHandler.get_indicators(QQQ).
                Must contain low, close, prior_close, ema21, sma50,
                prior_ema21, prior_sma50, sma50_n_days_ago.

        Returns:
            New regime state string.
        """
        if indicators is None:
            return self._state

        low = indicators["low"]
        close = indicators["close"]
        prior_close = indicators["prior_close"]
        ema21 = indicators["ema21"]
        sma50 = indicators["sma50"]
        sma50_n_ago = indicators["sma50_n_days_ago"]

        # Update streak counters
        if low > ema21:
            self._days_low_above_ema21 += 1
        else:
            self._days_low_above_ema21 = 0

        if ema21 > sma50:
            self._days_ema21_above_sma50 += 1
        else:
            self._days_ema21_above_sma50 = 0

        sma50_rising = (not config.REQUIRE_SMA50_RISING) or (sma50 > sma50_n_ago)
        up_day = (not config.REQUIRE_ACTIVATION_UPDAY) or (close > prior_close)

        # State transitions
        prev = self._state
        if self._state == config.REGIME_TREND_END:
            # Sticky terminal until activation conditions re-fire
            self._state = config.REGIME_NO_TREND

        if self._state in (config.REGIME_TREND_UP, config.REGIME_TREND_PRESSURE):
            # Deactivation: EMA21 crosses below SMA50
            if ema21 < sma50:
                self._state = config.REGIME_TREND_END
            elif self._state == config.REGIME_TREND_UP:
                # Slip into pressure if low breaks EMA21
                if config.ENABLE_TREND_PRESSURE and low < ema21:
                    self._state = config.REGIME_TREND_PRESSURE
            else:  # currently TREND_PRESSURE
                if low > ema21:
                    self._state = config.REGIME_TREND_UP

        if self._state == config.REGIME_NO_TREND:
            activation = (
                self._days_low_above_ema21 >= config.LOW_ABOVE_EMA_DAYS
                and self._days_ema21_above_sma50 >= config.EMA_ABOVE_SMA_DAYS
                and sma50_rising
                and up_day
            )
            if activation:
                self._state = config.REGIME_TREND_UP

        if prev != self._state:
            self._algo.debug(
                f"[REGIME] {prev} -> {self._state} "
                f"(low_above_ema21={self._days_low_above_ema21}d, "
                f"ema21_above_sma50={self._days_ema21_above_sma50}d)"
            )
        return self._state

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------
    @property
    def current_state(self) -> str:
        return self._state

    def entries_allowed(self) -> bool:
        """Entries permitted only in TREND_UP (or TREND_PRESSURE if enabled)."""
        if self._state == config.REGIME_TREND_UP:
            return True
        if (
            config.ENABLE_TREND_PRESSURE
            and self._state == config.REGIME_TREND_PRESSURE
        ):
            return True
        return False
