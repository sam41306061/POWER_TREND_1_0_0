"""
handlers/position_manager.py — Multi-Leg Position State

Tracks long equity positions with pyramid legs.
P&L is share-based (no options multiplier).

Contract:
  add_leg(...)               Record a filled entry or pyramid add
  close_trade(...)           Record a full exit
  active_trades              dict[symbol_str -> TradeRecord]
  can_add_position()         Under MAX_POSITIONS_OPEN limit
  has_position_for_underlying(symbol)
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import config


@dataclass
class Leg:
    fill_price: float
    quantity: int
    fill_date: date


@dataclass
class TradeRecord:
    symbol: str
    legs: list = field(default_factory=list)
    last_known_price: float = 0.0
    exit_price: float = 0.0
    exit_date: Optional[date] = None
    exit_reason: str = ""
    status: str = "OPEN"

    @property
    def total_quantity(self) -> int:
        return sum(l.quantity for l in self.legs)

    @property
    def leg_count(self) -> int:
        return len(self.legs)

    @property
    def avg_entry_price(self) -> float:
        qty = self.total_quantity
        if qty == 0:
            return 0.0
        return sum(l.fill_price * l.quantity for l in self.legs) / qty

    @property
    def last_leg_date(self) -> Optional[date]:
        return self.legs[-1].fill_date if self.legs else None

    @property
    def entry_date(self) -> Optional[date]:
        return self.legs[0].fill_date if self.legs else None


class PositionManager:
    """Multi-leg long equity tracker."""

    def __init__(self, algorithm):
        self._algo = algorithm
        self._trades: dict[str, TradeRecord] = {}
        self._closed_trades: list[TradeRecord] = []

    @property
    def active_trades(self) -> dict[str, TradeRecord]:
        return self._trades

    @property
    def closed_trades(self) -> list[TradeRecord]:
        return list(self._closed_trades)

    def can_add_position(self) -> bool:
        return len(self._trades) < config.MAX_POSITIONS_OPEN

    def has_position_for_underlying(self, symbol: str) -> bool:
        return symbol in self._trades

    def get_trade(self, symbol: str) -> Optional[TradeRecord]:
        return self._trades.get(symbol)

    def add_leg(
        self,
        symbol: str,
        fill_price: float,
        quantity: int,
        fill_date: date,
    ) -> TradeRecord:
        trade = self._trades.get(symbol)
        if trade is None:
            trade = TradeRecord(symbol=symbol)
            self._trades[symbol] = trade
        trade.legs.append(Leg(fill_price=fill_price, quantity=quantity, fill_date=fill_date))
        trade.last_known_price = fill_price
        self._algo.debug(
            f"[POSITION] {symbol} leg {trade.leg_count} qty={quantity} @ {fill_price:.2f} "
            f"(total {trade.total_quantity} @ avg {trade.avg_entry_price:.2f})"
        )
        return trade

    def close_trade(
        self, symbol: str, exit_price: float, reason: str
    ) -> Optional[dict]:
        trade = self._trades.pop(symbol, None)
        if trade is None:
            return None
        trade.exit_price = exit_price
        trade.exit_date = self._algo.time.date()
        trade.exit_reason = reason
        trade.status = "CLOSED"
        pnl = (exit_price - trade.avg_entry_price) * trade.total_quantity
        self._closed_trades.append(trade)
        return {
            "symbol": symbol,
            "pnl": pnl,
            "reason": reason,
            "avg_entry_price": trade.avg_entry_price,
            "exit_price": exit_price,
            "total_quantity": trade.total_quantity,
            "leg_count": trade.leg_count,
            "holding_days": (
                (trade.exit_date - trade.entry_date).days if trade.entry_date else 0
            ),
        }
