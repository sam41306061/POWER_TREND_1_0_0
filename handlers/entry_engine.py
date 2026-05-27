"""
handlers/entry_engine.py — Per-stock initial + add-on entry rules.

The QQQ regime gate and account drawdown gate are checked in main.py BEFORE
calling these methods. Each check is a pure function of today's indicator
dict (and, for adds, the open Trade record).

Initial entry (Gherkin: "Per-stock initial entry"):
  price > EMA21 > SMA50           bullish stack
  AND prior_low <= prior_EMA21    pullback touched EMA21 yesterday
  AND close >= open               blue bar

Add-on entry (Gherkin: "Pyramiding add-on entry"):
  prior_low <= prior_EMA21        pullback today
  AND prior bar AFTER last_leg_date   new pullback since last add
  AND close >= open               blue bar
"""

from typing import Optional


class EntryEngine:
    """Per-stock entry signal evaluator."""

    def __init__(self, algorithm):
        self._algo = algorithm

    # ---- Initial entry ------------------------------------------------

    def check_initial(self, indicators: Optional[dict]) -> bool:
        """True iff today's bar satisfies the initial-entry rule."""
        if not indicators:
            return False
        close = indicators["close"]
        ema21 = indicators["EMA21"]
        sma50 = indicators["SMA50"]
        prior_low = indicators["prior_low"]
        prior_ema21 = indicators["prior_EMA21"]
        is_blue = bool(indicators["is_blue_bar"])

        if not (close > ema21 > sma50):
            return False
        if prior_low > prior_ema21:
            return False
        if not is_blue:
            return False
        return True

    # ---- Add-on entry -------------------------------------------------

    def check_addon(self, trade, indicators: Optional[dict]) -> bool:
        """True iff *trade* may take another leg this bar."""
        if trade is None or not indicators:
            return False
        prior_low = indicators["prior_low"]
        prior_ema21 = indicators["prior_EMA21"]
        is_blue = bool(indicators["is_blue_bar"])
        today = self._algo.time.date()

        if prior_low > prior_ema21:
            return False
        # New pullback: the pullback bar (yesterday) must be strictly AFTER
        # the date of the last leg. Same-day adds are blocked.
        if trade.last_leg_date is not None and today <= trade.last_leg_date:
            return False
        if not is_blue:
            return False
        return True
