"""
handlers/position_manager.py — Multi-leg position tracking with avg-cost.

Tracks per-symbol Trade records with:
  legs[]             — list of {entry_date, entry_price, quantity}
  total_quantity     — sum of leg quantities still open
  avg_entry_price    — volume-weighted across open legs
  leg_count          — count of legs added (pyramid depth)
  last_leg_date      — date of most recent add (for new-pullback gating)

Public API:
  add_leg(symbol, price, qty, date)
  reduce_position(symbol, qty, price, reason)   — partial exit (stretch-trim)
  close_trade(symbol, price, reason)            — full exit
  get_trade(symbol) -> Trade | None
  has_position(symbol) -> bool
  active_trades -> dict[symbol_str, Trade]
  open_count -> int
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import config


@dataclass
class TradeLeg:
    entry_date: date
    entry_price: float
    quantity: int


@dataclass
class Trade:
    """Multi-leg open position with avg-cost accounting."""

    symbol: str
    legs: list = field(default_factory=list)
    total_quantity: int = 0
    avg_entry_price: float = 0.0
    leg_count: int = 0
    last_leg_date: Optional[date] = None
    last_known_price: float = 0.0
    status: str = "OPEN"  # OPEN → CLOSED

    def _recompute(self) -> None:
        qty = sum(leg.quantity for leg in self.legs)
        if qty <= 0:
            self.total_quantity = 0
            self.avg_entry_price = 0.0
            return
        cost = sum(leg.quantity * leg.entry_price for leg in self.legs)
        self.total_quantity = qty
        self.avg_entry_price = cost / qty


@dataclass
class ClosedTrade:
    symbol: str
    avg_entry_price: float
    exit_price: float
    quantity: int
    exit_reason: str
    entry_date: date
    exit_date: date
    pnl: float


class PositionManager:
    """Multi-leg position book with avg-cost tracking."""

    def __init__(self, algorithm):
        self._algo = algorithm
        self._trades: dict[str, Trade] = {}
        self._closed: list[ClosedTrade] = []

    # ---- Accessors ----------------------------------------------------

    @property
    def active_trades(self) -> dict[str, Trade]:
        return self._trades

    @property
    def open_count(self) -> int:
        return len(self._trades)

    def has_position(self, symbol) -> bool:
        return str(symbol) in self._trades

    def get_trade(self, symbol) -> Optional[Trade]:
        return self._trades.get(str(symbol))

    def can_add_position(self) -> bool:
        return self.open_count < config.MAX_POSITIONS_OPEN

    # ---- Mutations ----------------------------------------------------

    def add_leg(self, symbol, price: float, quantity: int, leg_date: date) -> Trade:
        """Append a new leg; create the Trade if absent. Returns the Trade."""
        sym = str(symbol)
        trade = self._trades.get(sym)
        if trade is None:
            trade = Trade(symbol=sym)
            self._trades[sym] = trade
        trade.legs.append(
            TradeLeg(entry_date=leg_date, entry_price=price, quantity=quantity)
        )
        trade.leg_count += 1
        trade.last_leg_date = leg_date
        trade.last_known_price = price
        trade._recompute()
        self._algo.debug(
            f"[POS] add_leg {sym} #{trade.leg_count} qty={quantity} @ {price:.2f} "
            f"avg={trade.avg_entry_price:.2f} total={trade.total_quantity}"
        )
        return trade

    def reduce_position(
        self, symbol, quantity: int, price: float, reason: str
    ) -> Optional[dict]:
        """
        Partial exit. Reduces shares proportionally across legs (preserves
        avg_entry_price). Returns a fill summary dict or None if no position.
        """
        sym = str(symbol)
        trade = self._trades.get(sym)
        if trade is None or quantity <= 0:
            return None
        sell_qty = min(quantity, trade.total_quantity)
        if sell_qty <= 0:
            return None

        # Reduce each leg proportionally; integer rounding handled by tracking
        # the remaining "sell_qty" budget across legs.
        remaining = sell_qty
        scale = sell_qty / trade.total_quantity
        new_legs = []
        for leg in trade.legs:
            reduce_by = int(round(leg.quantity * scale))
            reduce_by = min(reduce_by, leg.quantity, remaining)
            remaining -= reduce_by
            kept = leg.quantity - reduce_by
            if kept > 0:
                new_legs.append(
                    TradeLeg(
                        entry_date=leg.entry_date,
                        entry_price=leg.entry_price,
                        quantity=kept,
                    )
                )
        # Distribute any leftover (rounding error) starting from largest leg.
        if remaining > 0:
            new_legs.sort(key=lambda lg: lg.quantity, reverse=True)
            for leg in new_legs:
                take = min(remaining, leg.quantity)
                leg.quantity -= take
                remaining -= take
                if remaining == 0:
                    break
            new_legs = [lg for lg in new_legs if lg.quantity > 0]

        trade.legs = new_legs
        trade._recompute()
        trade.last_known_price = price

        pnl = (price - trade.avg_entry_price) * sell_qty if trade.avg_entry_price else 0.0
        self._algo.debug(
            f"[POS] reduce {sym} sell_qty={sell_qty} @ {price:.2f} reason={reason} "
            f"remaining={trade.total_quantity}"
        )

        # If reduction took position to zero, promote to closed.
        if trade.total_quantity == 0:
            self._trades.pop(sym, None)
            self._closed.append(
                ClosedTrade(
                    symbol=sym,
                    avg_entry_price=trade.avg_entry_price,
                    exit_price=price,
                    quantity=sell_qty,
                    exit_reason=reason,
                    entry_date=trade.legs[0].entry_date if trade.legs else self._algo.time.date(),
                    exit_date=self._algo.time.date(),
                    pnl=pnl,
                )
            )

        return {
            "symbol": sym,
            "sold_quantity": sell_qty,
            "remaining_quantity": trade.total_quantity,
            "price": price,
            "reason": reason,
            "pnl": pnl,
        }

    def close_trade(self, symbol, price: float, reason: str) -> Optional[dict]:
        """Full exit at *price*. Returns a summary dict or None if no position."""
        sym = str(symbol)
        trade = self._trades.pop(sym, None)
        if trade is None:
            return None

        qty = trade.total_quantity
        pnl = (price - trade.avg_entry_price) * qty
        entry_date = trade.legs[0].entry_date if trade.legs else self._algo.time.date()
        exit_date = self._algo.time.date()
        self._closed.append(
            ClosedTrade(
                symbol=sym,
                avg_entry_price=trade.avg_entry_price,
                exit_price=price,
                quantity=qty,
                exit_reason=reason,
                entry_date=entry_date,
                exit_date=exit_date,
                pnl=pnl,
            )
        )
        self._algo.debug(
            f"[POS] close {sym} qty={qty} @ {price:.2f} reason={reason} pnl={pnl:.2f}"
        )
        return {
            "symbol": sym,
            "quantity": qty,
            "price": price,
            "reason": reason,
            "pnl": pnl,
            "avg_entry_price": trade.avg_entry_price,
            "holding_days": (exit_date - entry_date).days,
        }
