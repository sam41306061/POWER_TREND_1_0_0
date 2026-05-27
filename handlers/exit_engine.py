"""
handlers/exit_engine.py — Per-stock exit rules in priority order.

Priority 0 is a PARTIAL exit (stretch-trim) checked first. If it fires this
bar, the full-exit checks (Priorities 1–5) are skipped for that bar.

Priorities 1–5 are FULL exits in order:
  1. Account drawdown >= MAX_ACCOUNT_DRAWDOWN_PCT       (drawdown_breached flag)
  2. Stop loss:    price <= avg_entry * (1 - STOP_LOSS_PCT)
  3. Target profit: price >= avg_entry * (1 + TARGET_PROFIT_PCT)
  4. SMA breakdown: close < SMA50
  5. EMA cross:    EMA21 < SMA50
"""

from math import floor
from typing import Optional

import config


class ExitEngine:
    """Evaluate partial and full per-stock exit rules."""

    def __init__(self, algorithm):
        self._algo = algorithm

    # ---- Partial exit (Priority 0) ------------------------------------

    def check_partial(self, trade, indicators: Optional[dict]) -> Optional[dict]:
        """
        Return {"quantity": int, "reason": str} when the stretch-trim fires,
        else None.
        """
        if trade is None or not indicators or trade.total_quantity <= 0:
            return None
        if indicators["high_vs_sma10"] < config.WEBBY_RSI_STRETCH_LEVEL:
            return None
        trim_qty = int(floor(trade.total_quantity * config.PARTIAL_EXIT_TRIM_FRACTION))
        if trim_qty <= 0:
            return None
        return {"quantity": trim_qty, "reason": config.EXIT_REASON_STRETCH_TRIM}

    # ---- Full exit (Priorities 1–5) -----------------------------------

    def check_full(
        self,
        trade,
        indicators: Optional[dict],
        drawdown_breached: bool,
    ) -> Optional[str]:
        """Return the EXIT_REASON_* string of the first triggered rule, else None."""
        if trade is None or not indicators or trade.total_quantity <= 0:
            return None

        # Priority 1 — account drawdown
        if drawdown_breached:
            return config.EXIT_REASON_DRAWDOWN

        price = indicators["close"]
        avg = trade.avg_entry_price
        sma50 = indicators["SMA50"]
        ema21 = indicators["EMA21"]

        # Priority 2 — stop loss
        if avg > 0 and price <= avg * (1.0 - config.STOP_LOSS_PCT):
            return config.EXIT_REASON_STOP_LOSS

        # Priority 3 — target profit
        if avg > 0 and price >= avg * (1.0 + config.TARGET_PROFIT_PCT):
            return config.EXIT_REASON_TARGET_PROFIT

        # Priority 4 — SMA breakdown
        if price < sma50:
            return config.EXIT_REASON_SMA_BREAKDOWN

        # Priority 5 — EMA cross
        if ema21 < sma50:
            return config.EXIT_REASON_EMA_CROSS

        return None
