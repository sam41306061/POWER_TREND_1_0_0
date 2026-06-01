"""
handlers/pyramiding_manager.py — Equal-Size Leg Sizing & Add-On Eligibility

Each leg is a fixed fraction (INITIAL_LEG_SIZE_PCT) of CURRENT total
portfolio value, computed at the moment the leg is taken. Equal-size means
later legs use less of the portfolio in % terms after gains, by design.

Add-on eligibility (see STRATEGY_OVERVIEW.md "Entry rules → add-ons"):
    1. Existing open position
    2. legs_so_far <= PYRAMID_MAX_ADDS    (i.e. room for one more leg)
    3. Add only on a different bar than the last leg
    4. Stock still in TREND_UP per its own EMA21/SMA50
    5. Today's bar is a blue-bar (close >= open)
    6. Regime gate still allows entries
"""

from __future__ import annotations

import math

import config


class PyramidingManager:
    """Compute leg sizes and decide whether an add-on is permitted."""

    def __init__(self, algorithm):
        self._algo = algorithm

    # ------------------------------------------------------------------
    # Sizing
    # ------------------------------------------------------------------
    def leg_quantity(self, price: float) -> int:
        """Return integer share count for one leg sized at INITIAL_LEG_SIZE_PCT."""
        if price <= 0:
            return 0
        equity = float(self._algo.portfolio.total_portfolio_value)
        dollars = equity * config.INITIAL_LEG_SIZE_PCT
        return int(math.floor(dollars / price))

    # ------------------------------------------------------------------
    # Add-on gating
    # ------------------------------------------------------------------
    def can_add_leg(self, trade, indicators: dict) -> tuple[bool, str]:
        """
        Decide whether to add a leg to an EXISTING position today.

        Args:
            trade: TradeRecord
            indicators: today's indicator dict for the symbol

        Returns:
            (allowed, reason). reason is a short diagnostic string.
        """
        today = self._algo.time.date()

        # 1+2. Room for another leg
        if trade.leg_count >= 1 + config.PYRAMID_MAX_ADDS:
            return False, "max_legs"

        # 3. Different bar than last leg
        if trade.last_leg_date == today:
            return False, "same_bar_as_last_leg"

        # 4. Stock-level trend: EMA21 > SMA50 (and price above EMA21)
        if indicators["ema21"] <= indicators["sma50"]:
            return False, "stock_not_trending"
        if indicators["close"] <= indicators["ema21"]:
            return False, "close_below_ema21"

        # 5. Blue bar requirement
        if not indicators.get("is_blue_bar", False):
            return False, "not_blue_bar"

        return True, "ok"
