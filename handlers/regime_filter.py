"""
handlers/regime_filter.py — QQQ Power Trend state machine.

Implements Webster's four strict activation rules plus the market-school
`TREND_PRESSURE` extension. Rolling counters are updated *incrementally* once
per trading day from QQQ indicators — never recomputed by re-scanning history.

States: NO_TREND, TREND_UP, TREND_PRESSURE, TREND_END.
Only TREND_UP allows new entries.

See STRATEGY_OVERVIEW.md → "Power Trend Definition" for the full contract.
"""

from typing import Optional

import config


class RegimeFilter:
    """Stateful Power Trend classifier driven by daily QQQ indicators."""

    def __init__(self, algorithm):
        self._algo = algorithm
        # Rolling counters / one-bar flags.
        self.days_low_above_ema21: int = 0
        self.days_ema21_above_sma50: int = 0
        self.sma50_rising: bool = False
        self.is_blue_bar: bool = False
        # Current state.
        self.current_state: str = config.REGIME_NO_TREND
        # Track the date of the last update to avoid double-counting same bar.
        self._last_update_date = None

    # ------------------------------------------------------------------ #

    def update(self, qqq_indicators: Optional[dict]) -> None:
        """Advance the state machine using today's QQQ indicator dict."""
        if qqq_indicators is None:
            return
        today = self._algo.time.date()
        if self._last_update_date == today:
            return
        self._last_update_date = today

        low = qqq_indicators["low"]
        ema21 = qqq_indicators["EMA21"]
        sma50 = qqq_indicators["SMA50"]
        prior_sma50 = qqq_indicators["prior_SMA50"]
        close = qqq_indicators["close"]
        is_blue = bool(qqq_indicators["is_blue_bar"])

        # ---- Update rolling counters ----
        if low > ema21:
            self.days_low_above_ema21 += 1
        else:
            self.days_low_above_ema21 = 0

        if ema21 > sma50:
            self.days_ema21_above_sma50 += 1
        else:
            self.days_ema21_above_sma50 = 0

        self.sma50_rising = sma50 > prior_sma50
        self.is_blue_bar = is_blue

        # ---- State machine transitions ----
        self.current_state = self._next_state(close, ema21, sma50)

    def entries_allowed(self) -> bool:
        """True iff regime is TREND_UP (the only state that opens new entries)."""
        return self.current_state == config.REGIME_TREND_UP

    # ------------------------------------------------------------------ #

    def _activation_rules_met(self) -> bool:
        """Strict 4-rule activation, honoring lite-mode toggles."""
        if self.days_low_above_ema21 < config.LOW_ABOVE_EMA_DAYS:
            return False
        if self.days_ema21_above_sma50 < config.EMA_ABOVE_SMA_DAYS:
            return False
        if config.REQUIRE_SMA50_RISING and not self.sma50_rising:
            return False
        if config.REQUIRE_ACTIVATION_UPDAY and not self.is_blue_bar:
            return False
        return True

    def _next_state(self, close: float, ema21: float, sma50: float) -> str:
        state = self.current_state

        # TREND_END is terminal for one bar; collapse to NO_TREND immediately
        # so re-activation can fire on the same evaluation (re-activation policy).
        if state == config.REGIME_TREND_END:
            state = config.REGIME_NO_TREND

        if state == config.REGIME_NO_TREND:
            if self._activation_rules_met():
                return config.REGIME_TREND_UP
            return config.REGIME_NO_TREND

        if state == config.REGIME_TREND_UP:
            # Hard deactivation: official cross-back.
            if ema21 < sma50:
                return config.REGIME_TREND_END
            # Pressure: first break of 50-day while EMA still above SMA.
            if config.ENABLE_TREND_PRESSURE and close < sma50 and ema21 > sma50:
                return config.REGIME_TREND_PRESSURE
            return config.REGIME_TREND_UP

        if state == config.REGIME_TREND_PRESSURE:
            if ema21 < sma50:
                return config.REGIME_TREND_END
            # Re-arm: close back above EMA21 and EMA21 still above SMA50.
            if close > ema21 and ema21 > sma50:
                return config.REGIME_TREND_UP
            return config.REGIME_TREND_PRESSURE

        return state
