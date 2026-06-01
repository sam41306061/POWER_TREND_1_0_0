"""
handlers/position_manager.py — Multi-Leg Position Tracking

Equity-only (no options multiplier). Each open position is a `TradeRecord`
composed of one or more equal-size `Leg`s added by the pyramiding manager.

Lifecycle:
    open_position(...)            # First leg
    add_leg(...)                  # Subsequent pyramid adds
    reduce_position(...)          # Partial trim (e.g. stretch-trim)
    close_position(...)           # Full exit
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import config


# ----------------------------------------------------------------------
# Symbol identity helper
# ----------------------------------------------------------------------


def _symbol_key(symbol) -> str:
    """Return canonical ticker string for use as a dict key.

    QC `Symbol` instances are not reliably hash-equal across universe
    refreshes for the same underlying ticker. Always normalise to the
    upper-cased ticker (``Symbol.value`` on QC, first whitespace token
    on plain-string test doubles). See architecture-rules.md
    "Symbol Identity".
    """
    val = getattr(symbol, "value", None)
    if val is not None:
        return str(val).upper()
    return str(symbol).split()[0].upper()


# ----------------------------------------------------------------------
# Data classes
# ----------------------------------------------------------------------


@dataclass
class Leg:
    """A single pyramid leg fill."""

    entry_price: float
    quantity: int
    entry_date: date


@dataclass
class TradeRecord:
    """Aggregate open (or closed) position composed of one or more legs."""

    symbol: object                 # QC Symbol (or str in tests)
    legs: list[Leg] = field(default_factory=list)
    # Mutable state
    last_known_price: float = 0.0
    exit_price: float = 0.0
    exit_date: Optional[date] = None
    exit_reason: str = ""
    status: str = "OPEN"           # OPEN -> CLOSED
    # Realised partial-exit P/L (accumulates as we trim)
    realized_pnl: float = 0.0

    # ----- Derived properties -----
    @property
    def total_quantity(self) -> int:
        return sum(l.quantity for l in self.legs)

    @property
    def leg_count(self) -> int:
        return len(self.legs)

    @property
    def avg_entry_price(self) -> float:
        qty = self.total_quantity
        if qty <= 0:
            return 0.0
        cost = sum(l.entry_price * l.quantity for l in self.legs)
        return cost / qty

    @property
    def last_leg_date(self) -> Optional[date]:
        if not self.legs:
            return None
        return max(l.entry_date for l in self.legs)

    @property
    def entry_date(self) -> Optional[date]:
        if not self.legs:
            return None
        return min(l.entry_date for l in self.legs)


# ----------------------------------------------------------------------
# Manager
# ----------------------------------------------------------------------


class PositionManager:
    """Track open positions and lifecycle transitions."""

    def __init__(self, algorithm):
        self._algo = algorithm
        # Keyed on canonical ticker string (see _symbol_key) — NOT raw QC Symbol
        # objects, which can differ across universe refreshes for the same ticker.
        self._trades: dict[str, TradeRecord] = {}
        self._closed_trades: list[TradeRecord] = []

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------
    @property
    def active_trades(self) -> dict[str, TradeRecord]:
        return self._trades

    @property
    def closed_trades(self) -> list[TradeRecord]:
        return list(self._closed_trades)

    def has_position(self, symbol) -> bool:
        return _symbol_key(symbol) in self._trades

    def can_add_position(self) -> bool:
        return len(self._trades) < config.MAX_POSITIONS_OPEN

    def get(self, symbol) -> Optional[TradeRecord]:
        return self._trades.get(_symbol_key(symbol))

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------
    def open_position(
        self, symbol, fill_price: float, quantity: int, entry_date: date
    ) -> TradeRecord:
        """Create a new position with its first leg."""
        key = _symbol_key(symbol)
        if key in self._trades:
            raise ValueError(f"Position already open for {symbol}")
        trade = TradeRecord(symbol=symbol, last_known_price=fill_price)
        trade.legs.append(
            Leg(entry_price=fill_price, quantity=quantity, entry_date=entry_date)
        )
        self._trades[key] = trade
        self._algo.debug(
            f"[POSITION] OPEN {symbol} leg=1 qty={quantity} @ {fill_price:.2f}"
        )
        return trade

    def add_leg(
        self, symbol, fill_price: float, quantity: int, entry_date: date
    ) -> TradeRecord:
        """Append a pyramid leg to an existing position."""
        trade = self._trades.get(_symbol_key(symbol))
        if trade is None:
            raise ValueError(f"No open position for {symbol}")
        if trade.leg_count >= 1 + config.PYRAMID_MAX_ADDS:
            raise ValueError(
                f"{symbol} already at max legs ({trade.leg_count})"
            )
        trade.legs.append(
            Leg(entry_price=fill_price, quantity=quantity, entry_date=entry_date)
        )
        trade.last_known_price = fill_price
        self._algo.debug(
            f"[POSITION] ADD {symbol} leg={trade.leg_count} qty={quantity} "
            f"@ {fill_price:.2f} avg={trade.avg_entry_price:.2f}"
        )
        return trade

    def reduce_position(
        self,
        symbol,
        sell_quantity: int,
        sell_price: float,
        reason: str,
    ) -> Optional[dict]:
        """
        Partial exit. Reduces legs FIFO and records realised P/L.
        Returns trim summary or None if no position.
        """
        trade = self._trades.get(_symbol_key(symbol))
        if trade is None or sell_quantity <= 0:
            return None

        remaining = sell_quantity
        realised = 0.0
        # FIFO consume legs
        new_legs: list[Leg] = []
        for leg in trade.legs:
            if remaining <= 0:
                new_legs.append(leg)
                continue
            if leg.quantity <= remaining:
                realised += (sell_price - leg.entry_price) * leg.quantity
                remaining -= leg.quantity
            else:
                realised += (sell_price - leg.entry_price) * remaining
                new_legs.append(
                    Leg(
                        entry_price=leg.entry_price,
                        quantity=leg.quantity - remaining,
                        entry_date=leg.entry_date,
                    )
                )
                remaining = 0
        trade.legs = new_legs
        trade.realized_pnl += realised
        trade.last_known_price = sell_price

        sold_qty = sell_quantity - remaining
        self._algo.debug(
            f"[POSITION] TRIM {symbol} -{sold_qty} @ {sell_price:.2f} "
            f"reason={reason} realised={realised:+.2f}"
        )

        if trade.total_quantity <= 0:
            return self.close_position(symbol, sell_price, reason)

        return {
            "symbol": symbol,
            "trim_quantity": sold_qty,
            "trim_price": sell_price,
            "reason": reason,
            "realized_pnl": realised,
            "remaining_quantity": trade.total_quantity,
        }

    def close_position(
        self, symbol, exit_price: float, reason: str
    ) -> Optional[dict]:
        """Fully close a position and move it to closed history."""
        trade = self._trades.pop(_symbol_key(symbol), None)
        if trade is None:
            return None

        qty = trade.total_quantity
        realised_final = (exit_price - trade.avg_entry_price) * qty
        total_realised = trade.realized_pnl + realised_final

        trade.exit_price = exit_price
        trade.exit_date = self._algo.time.date()
        trade.exit_reason = reason
        trade.status = "CLOSED"
        trade.realized_pnl = total_realised
        self._closed_trades.append(trade)

        holding_days = 0
        if trade.entry_date and trade.exit_date:
            holding_days = (trade.exit_date - trade.entry_date).days

        self._algo.debug(
            f"[POSITION] CLOSE {symbol} qty={qty} @ {exit_price:.2f} "
            f"reason={reason} pnl={total_realised:+.2f}"
        )
        return {
            "symbol": symbol,
            "exit_price": exit_price,
            "exit_quantity": qty,
            "reason": reason,
            "pnl": total_realised,
            "avg_entry_price": trade.avg_entry_price,
            "holding_days": holding_days,
            "leg_count": trade.leg_count,
        }
