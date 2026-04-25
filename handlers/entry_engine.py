"""
handlers/entry_engine.py — Per-stock initial + add-on entry rules.

Initial entry:
  regime.entries_allowed()
  AND risk.is_new_entry_allowed()
  AND under MAX_POSITIONS_OPEN
  AND not has_position(symbol)
  AND price > EMA21 > SMA50
  AND prior_low <= prior_EMA21
  AND close >= open  (blue bar)

Add-on:
  regime.entries_allowed()
  AND has_position(symbol)
  AND leg_count < 1 + PYRAMID_MAX_ADDS
  AND prior_low <= prior_EMA21 AND prior_close > last_leg_date
  AND close >= open
"""

from typing import Optional


class EntrySignal:
    INITIAL = "INITIAL"
    ADD = "ADD"


class EntryEngine:
    def __init__(self, algorithm, regime, risk, position_manager, pyramiding):
        self._algo = algorithm
        self._regime = regime
        self._risk = risk
        self._positions = position_manager
        self._pyramiding = pyramiding

    def evaluate(self, symbol: str, indicators: dict) -> Optional[str]:
        """Return EntrySignal.INITIAL, EntrySignal.ADD, or None."""
        if not indicators:
            return None
        if not self._regime.entries_allowed():
            return None
        if not self._risk.is_new_entry_allowed():
            return None
        if not indicators.get("is_blue_bar", False):
            return None

        close = indicators["close"]
        ema = indicators["EMA21"]
        sma = indicators["SMA50"]
        prior_low = indicators["prior_low"]
        prior_ema = indicators["prior_EMA21"]

        # Bullish stack required for both initial and add-on
        if not (close > ema > sma):
            return None

        # Pullback in prior bar
        if not (prior_low <= prior_ema):
            return None

        trade = self._positions.get_trade(symbol)
        if trade is None:
            if not self._positions.can_add_position():
                return None
            return EntrySignal.INITIAL

        # Add-on: cap + new pullback after last leg
        if not self._pyramiding.can_add_more(trade.leg_count):
            return None
        last_leg = trade.last_leg_date
        today = self._algo.time.date()
        if last_leg is not None and today <= last_leg:
            return None
        return EntrySignal.ADD
