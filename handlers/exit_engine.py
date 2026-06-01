"""
handlers/exit_engine.py — Priority-Ordered Exit Decisions

Per STRATEGY_OVERVIEW.md the daily exit pass evaluates rules in strict
priority order. The first rule that fires for a given position wins.

Priority 0  PARTIAL  Stretch-trim
    atr_stretch_low > WEBBY_RSI_STRETCH_LEVEL  (extreme extension)
    -> trim PARTIAL_EXIT_TRIM_FRACTION of total_quantity at current close.

Priority 1  FULL     Account drawdown (forced liquidation everywhere)
    risk_manager.current_drawdown >= MAX_ACCOUNT_DRAWDOWN_PCT
    NOTE: this is enforced by main.py *before* per-symbol exits run; the
    engine still returns an ACCOUNT_DRAWDOWN reason if invoked directly so
    callers cannot miss it.

Priority 2  FULL     Stop-loss
    close < avg_entry_price * (1 - STOP_LOSS_PCT)

Priority 3  FULL     SMA50 breakdown
    close < sma50

Priority 4  FULL     EMA21 / SMA50 bearish cross
    ema21 < sma50  (regime-style breakdown at the stock level)

Engine emits a list of ExitDecision objects. main.py applies them.
"""

from __future__ import annotations

from dataclasses import dataclass

import config


@dataclass(frozen=True)
class ExitDecision:
    symbol: object
    kind: str                # "FULL" or "PARTIAL"
    quantity: int            # shares to sell
    reason: str
    indicators: dict


class ExitEngine:
    """Generate exit/trim decisions for the day."""

    def __init__(self, algorithm, position_manager, risk_manager, data_handler):
        self._algo = algorithm
        self._pos = position_manager
        self._risk = risk_manager
        self._data = data_handler

    # ------------------------------------------------------------------
    # Main exit pass
    # ------------------------------------------------------------------
    def generate_exits(self) -> list[ExitDecision]:
        decisions: list[ExitDecision] = []

        # Account-level drawdown forces liquidation across the board.
        if self._risk.current_drawdown >= config.MAX_ACCOUNT_DRAWDOWN_PCT:
            for trade in list(self._pos.active_trades.values()):
                symbol = trade.symbol
                ind = self._data.get_indicators(symbol) or {}
                decisions.append(
                    ExitDecision(
                        symbol=symbol, kind="FULL",
                        quantity=trade.total_quantity,
                        reason=config.EXIT_REASON_DRAWDOWN,
                        indicators=ind,
                    )
                )
            return decisions

        for trade in list(self._pos.active_trades.values()):
            symbol = trade.symbol
            ind = self._data.get_indicators(symbol)
            if ind is None:
                continue

            # Priority 0 — partial stretch-trim
            if ind["atr_stretch_low"] > config.WEBBY_RSI_STRETCH_LEVEL:
                trim_qty = int(
                    round(trade.total_quantity * config.PARTIAL_EXIT_TRIM_FRACTION)
                )
                if trim_qty > 0 and trim_qty < trade.total_quantity:
                    decisions.append(
                        ExitDecision(
                            symbol=symbol, kind="PARTIAL",
                            quantity=trim_qty,
                            reason=config.EXIT_REASON_STRETCH_TRIM,
                            indicators=ind,
                        )
                    )
                    # Do NOT skip subsequent full-exit checks — both can co-fire.

            # Priority 2 — stop loss
            avg = trade.avg_entry_price
            if avg > 0 and ind["close"] < avg * (1.0 - config.STOP_LOSS_PCT):
                decisions.append(
                    ExitDecision(
                        symbol=symbol, kind="FULL",
                        quantity=trade.total_quantity,
                        reason=config.EXIT_REASON_STOP_LOSS,
                        indicators=ind,
                    )
                )
                continue

            # Priority 3 — SMA50 breakdown
            if ind["close"] < ind["sma50"]:
                decisions.append(
                    ExitDecision(
                        symbol=symbol, kind="FULL",
                        quantity=trade.total_quantity,
                        reason=config.EXIT_REASON_SMA_BREAKDOWN,
                        indicators=ind,
                    )
                )
                continue

            # Priority 4 — EMA21/SMA50 bearish cross
            if ind["ema21"] < ind["sma50"]:
                decisions.append(
                    ExitDecision(
                        symbol=symbol, kind="FULL",
                        quantity=trade.total_quantity,
                        reason=config.EXIT_REASON_EMA_CROSS,
                        indicators=ind,
                    )
                )
                continue

        return decisions
