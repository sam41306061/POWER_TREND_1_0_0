"""
handlers/entry_engine.py — Initial + Add-On Entry Decisions

Two entry types:

    INITIAL  — open a brand new position (first leg)
    ADD_ON   — append a leg to an existing position (pyramiding)

Initial entry filter (all must be true):
    - Regime: regime filter allows entries (TREND_UP / TREND_PRESSURE)
    - Risk:   risk manager allows new entries (DD gate)
    - Capacity: position_manager.can_add_position()
    - Stock-level trend: ema21 > sma50 AND close > ema21
    - Today is a blue bar
    - Yesterday's bar already broke above SMA10 (entry trigger)
      i.e. prior_close > sma10 today (close confirms above SMA10)

Add-on entry filter:
    delegated to PyramidingManager.can_add_leg()

The engine returns a list of (symbol, EntryDecision) pairs. It does NOT
place orders — main.py is responsible for SDK calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import config


@dataclass(frozen=True)
class EntryDecision:
    symbol: object
    kind: str               # "INITIAL" or "ADD_ON"
    target_quantity: int
    indicators: dict


class EntryEngine:
    """Generate entry decisions for the day."""

    def __init__(
        self,
        algorithm,
        position_manager,
        regime_filter,
        risk_manager,
        pyramiding_manager,
        data_handler,
    ):
        self._algo = algorithm
        self._pos = position_manager
        self._regime = regime_filter
        self._risk = risk_manager
        self._pyramid = pyramiding_manager
        self._data = data_handler

    # ------------------------------------------------------------------
    # Main entry-pass
    # ------------------------------------------------------------------
    def generate_entries(self, universe: Iterable) -> list[EntryDecision]:
        if not self._regime.entries_allowed():
            return []
        if not self._risk.is_new_entry_allowed():
            self._algo.debug(
                f"[ENTRY] Blocked by drawdown gate "
                f"(DD={self._risk.current_drawdown:.2%})"
            )
            return []

        decisions: list[EntryDecision] = []

        # 1) Add-ons for existing positions take priority.
        # active_trades is keyed on ticker-string; use trade.symbol (preserved
        # original QC Symbol) for indicator + order references.
        for trade in list(self._pos.active_trades.values()):
            symbol = trade.symbol
            ind = self._data.get_indicators(symbol)
            if ind is None:
                continue
            ok, _reason = self._pyramid.can_add_leg(trade, ind)
            if not ok:
                continue
            qty = self._pyramid.leg_quantity(ind["close"])
            if qty <= 0:
                continue
            decisions.append(
                EntryDecision(
                    symbol=symbol, kind="ADD_ON",
                    target_quantity=qty, indicators=ind,
                )
            )

        # 2) Initial entries for new symbols
        #
        # IMPORTANT: PositionManager._trades only updates inside on_order_event
        # (asynchronously, after _evaluate returns), so self._pos.can_add_position()
        # reads pre-loop state. We must track decisions appended *within this loop*
        # locally to enforce MAX_POSITIONS_OPEN. See architecture-rules.md
        # "Decisions vs. Settled State".
        pending_initial = 0
        settled_count = len(self._pos.active_trades)
        for symbol in universe:
            if self._pos.has_position(symbol):
                continue
            if settled_count + pending_initial >= config.MAX_POSITIONS_OPEN:
                break
            if str(symbol).upper().startswith(config.REGIME_SYMBOL.upper()):
                continue
            ind = self._data.get_indicators(symbol)
            if ind is None:
                continue
            if not self._is_initial_entry_valid(ind):
                continue
            qty = self._pyramid.leg_quantity(ind["close"])
            if qty <= 0:
                continue
            decisions.append(
                EntryDecision(
                    symbol=symbol, kind="INITIAL",
                    target_quantity=qty, indicators=ind,
                )
            )
            pending_initial += 1

        return decisions

    # ------------------------------------------------------------------
    # Rules
    # ------------------------------------------------------------------
    @staticmethod
    def _is_initial_entry_valid(ind: dict) -> bool:
        # Stock-level trend
        if ind["ema21"] <= ind["sma50"]:
            return False
        if ind["close"] <= ind["ema21"]:
            return False
        # Blue bar today
        if not ind.get("is_blue_bar", False):
            return False
        # SMA10 breakout: today's close above SMA10 AND prior close above SMA10
        if ind["close"] <= ind["sma10"]:
            return False
        if ind["prior_close"] <= ind["sma10"]:
            return False
        return True
