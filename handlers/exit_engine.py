"""
handlers/exit_engine.py — Option-aware exit checks.

Evaluation returns a list of (leg_or_None, reason) tuples. A `leg=None`
result means "close ALL legs of the trade" (trade-wide rule). A specific
leg means "close only that leg" (per-leg rule).

Priority (per-leg rules evaluated first, in this order):
  1. DTE_FORCE_CLOSE   — leg.expiry within OPTION_FORCE_EXIT_DAYS_BEFORE_EXPIRY
  2. PREMIUM_STOP_LOSS — current option mid <= leg.fill_price * (1 - X)

Trade-wide rules (any one fires, the entire TradeRecord unwinds):
  3. ACCOUNT_DRAWDOWN  — risk.drawdown >= MAX_ACCOUNT_DRAWDOWN_PCT
  4. SMA_BREAKDOWN     — underlying close < SMA50
  5. EMA_CROSS         — EMA21 < SMA50

The engine itself stays LEAN-free; current option premia must be supplied
via an injected `premium_lookup(contract_symbol) -> float` callable.
"""

from datetime import date as _date
from typing import Callable, List, Optional, Tuple

import config


PremiumLookup = Callable[[object], float]


class ExitEngine:
    def __init__(self, algorithm, risk):
        self._algo = algorithm
        self._risk = risk

    def check(
        self,
        trade,
        indicators: Optional[dict],
        today: Optional[_date] = None,
        premium_lookup: Optional[PremiumLookup] = None,
    ) -> List[Tuple[Optional[object], str]]:
        """
        Return a list of (leg_or_None, reason) decisions.
          - (leg, reason): close just that leg
          - (None, reason): close the entire trade (all open legs)
        Multiple per-leg decisions may be returned in the same call.
        Trade-wide rules short-circuit and return a single (None, reason).
        """
        if today is None:
            today = self._algo.time.date()

        # ---------- Trade-wide rules (highest precedence) ----------
        if self._risk.drawdown >= config.MAX_ACCOUNT_DRAWDOWN_PCT:
            return [(None, config.EXIT_REASON_DRAWDOWN)]

        if indicators:
            close = indicators.get("close")
            ema = indicators.get("EMA21")
            sma = indicators.get("SMA50")
            if close is not None and sma is not None and close < sma:
                return [(None, config.EXIT_REASON_SMA_BREAKDOWN)]
            if ema is not None and sma is not None and ema < sma:
                return [(None, config.EXIT_REASON_EMA_CROSS)]

        # ---------- Per-leg rules ----------
        decisions: List[Tuple[Optional[object], str]] = []
        for leg in list(trade.open_legs):
            # 1. DTE force close
            if leg.expiry is not None:
                dte = (leg.expiry - today).days
                if dte <= config.OPTION_FORCE_EXIT_DAYS_BEFORE_EXPIRY:
                    decisions.append((leg, config.EXIT_REASON_DTE_FORCE))
                    continue
            # 2. Premium stop loss
            if premium_lookup is not None and leg.fill_price > 0:
                try:
                    current_mid = float(premium_lookup(leg.contract_symbol))
                except Exception:  # noqa: BLE001 — lookup must never break the loop
                    current_mid = 0.0
                if current_mid > 0:
                    threshold = leg.fill_price * (1.0 - config.OPTION_PREMIUM_STOP_LOSS_PCT)
                    if current_mid <= threshold:
                        decisions.append((leg, config.EXIT_REASON_PREMIUM_STOP))

        return decisions
