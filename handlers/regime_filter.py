"""
handlers/regime_filter.py — QQQ Power Trend State Machine

States: NO_TREND, TREND_UP, TREND_PRESSURE, TREND_END
Activation rules (strict, all on same bar):
  1. days_low_above_ema21 >= LOW_ABOVE_EMA_DAYS
  2. days_ema21_above_sma50 >= EMA_ABOVE_SMA_DAYS
  3. sma50_rising (today.SMA50 > yesterday.SMA50)         [if REQUIRE_SMA50_RISING]
  4. is_blue_bar (close >= open)                          [if REQUIRE_ACTIVATION_UPDAY]

Counters are stateful and incremented one bar at a time. Never re-scan history.
"""

import config


class RegimeFilter:
    """Stateful Power Trend classifier driven by daily QQQ indicators."""

    def __init__(self, algorithm):
        self._algo = algorithm
        self.current_state: str = config.REGIME_NO_TREND
        self.days_low_above_ema21: int = 0
        self.days_ema21_above_sma50: int = 0
        self.sma50_rising: bool = False
        self.is_blue_bar: bool = False

    # ------------------------------------------------------------------
    def update(self, qqq: dict) -> str:
        """Advance counters and state. Returns the new `current_state`."""
        if not qqq:
            return self.current_state

        # Counters
        self.days_low_above_ema21 = (
            self.days_low_above_ema21 + 1 if qqq["low"] > qqq["EMA21"] else 0
        )
        self.days_ema21_above_sma50 = (
            self.days_ema21_above_sma50 + 1 if qqq["EMA21"] > qqq["SMA50"] else 0
        )
        self.sma50_rising = qqq["SMA50"] > qqq["prior_SMA50"]
        self.is_blue_bar = qqq["is_blue_bar"]

        self._transition(qqq)
        return self.current_state

    # ------------------------------------------------------------------
    def _transition(self, qqq: dict) -> None:
        state = self.current_state

        if state == config.REGIME_TREND_END:
            # Terminal label exists for one bar; reset to NO_TREND, allow same-bar re-arm
            state = config.REGIME_NO_TREND

        if state in (config.REGIME_TREND_UP, config.REGIME_TREND_PRESSURE):
            # Deactivation: EMA21 cross-back below SMA50
            if qqq["EMA21"] < qqq["SMA50"]:
                self.current_state = config.REGIME_TREND_END
                return

        if state == config.REGIME_TREND_UP:
            if config.ENABLE_TREND_PRESSURE:
                if qqq["close"] < qqq["SMA50"] and qqq["EMA21"] > qqq["SMA50"]:
                    self.current_state = config.REGIME_TREND_PRESSURE
                    return
            self.current_state = config.REGIME_TREND_UP
            return

        if state == config.REGIME_TREND_PRESSURE:
            if qqq["close"] > qqq["EMA21"] and qqq["EMA21"] > qqq["SMA50"]:
                self.current_state = config.REGIME_TREND_UP
                return
            self.current_state = config.REGIME_TREND_PRESSURE
            return

        # state == NO_TREND: check activation
        if self._activation_met(qqq):
            self.current_state = config.REGIME_TREND_UP
        else:
            self.current_state = config.REGIME_NO_TREND

    def _activation_met(self, qqq: dict) -> bool:
        if self.days_low_above_ema21 < config.LOW_ABOVE_EMA_DAYS:
            return False
        if self.days_ema21_above_sma50 < config.EMA_ABOVE_SMA_DAYS:
            return False
        if config.REQUIRE_SMA50_RISING and not self.sma50_rising:
            return False
        if config.REQUIRE_ACTIVATION_UPDAY and not self.is_blue_bar:
            return False
        return True

    # ------------------------------------------------------------------
    def entries_allowed(self) -> bool:
        return self.current_state == config.REGIME_TREND_UP
