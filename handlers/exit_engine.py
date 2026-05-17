"""
handlers/exit_engine.py — Per-stock exit checks (priority-ordered).

Priority:
  0. Stretch-trim partial: high_vs_sma10 >= WEBBY_RSI_STRETCH_LEVEL (partial sell)
  1. Account drawdown >= MAX_ACCOUNT_DRAWDOWN_PCT
  2. Stop loss: price <= avg_entry_price * (1 - STOP_LOSS_PCT)
  3. Daily close < SMA50
  4. EMA21 < SMA50
"""

from typing import Optional, Tuple

import config


class ExitEngine:
    def __init__(self, algorithm, risk):
        self._algo = algorithm
        self._risk = risk

    def check_partial(self, trade, indicators: dict) -> Tuple[bool, Optional[str]]:
        """Return (should_trim, reason) for stretch-trim partial exit (Priority 0)."""
        if not indicators:
            return False, None
        if indicators.get("high_vs_sma10", 0.0) >= config.WEBBY_RSI_STRETCH_LEVEL:
            return True, config.EXIT_REASON_STRETCH_TRIM
        return False, None

    def check(self, trade, indicators: dict) -> Tuple[bool, Optional[str]]:
        """Return (should_exit, reason)."""
        # 1. Account drawdown
        if self._risk.drawdown >= config.MAX_ACCOUNT_DRAWDOWN_PCT:
            return True, config.EXIT_REASON_DRAWDOWN

        if not indicators:
            return False, None

        close = indicators["close"]
        ema = indicators["EMA21"]
        sma = indicators["SMA50"]

        # 2. Stop loss
        avg = trade.avg_entry_price
        if avg > 0 and close <= avg * (1 - config.STOP_LOSS_PCT):
            return True, config.EXIT_REASON_STOP_LOSS

        # 3. SMA breakdown
        if close < sma:
            return True, config.EXIT_REASON_SMA_BREAKDOWN

        # 4. EMA cross
        if ema < sma:
            return True, config.EXIT_REASON_EMA_CROSS

        return False, None
