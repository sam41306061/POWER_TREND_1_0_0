"""
handlers/position_manager.py — Position State Machine & Exit Logic

Responsibility:
  Track open positions, evaluate exit conditions, manage trade lifecycle.

State Machine:
  PENDING → OPEN → CLOSED

Contract:
  add_trade(...)                 Record a new filled entry
  close_trade(...)               Record a closed position
  check_exit_conditions(...)     Evaluate exit rules in priority order
  can_add_position() → bool      Under MAX_POSITIONS_OPEN limit?
  has_position_for_underlying()  Duplicate check by underlying symbol
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import config


@dataclass
class TradeRecord:
    """Internal position record for tracking open/closed trades."""

    symbol: str  # Underlying equity symbol
    instrument_symbol: str  # Actual traded symbol (option contract, etc.)
    entry_price: float
    entry_date: date
    trade_type: str  # Strategy identifier (e.g., "SETUP", "BREAKOUT")
    quantity: int
    total_cost: float
    target_delta: float = 0.0

    # Mutable state (updated during lifetime)
    last_known_price: float = 0.0
    current_delta: float = 0.0
    exit_price: float = 0.0
    exit_date: Optional[date] = None
    exit_reason: str = ""
    status: str = "OPEN"  # OPEN → CLOSED


class PositionManager:
    """Track positions and evaluate exit conditions."""

    def __init__(self, algorithm):
        self._algo = algorithm
        self._trades: dict[str, TradeRecord] = {}  # {instrument_symbol: TradeRecord}
        self._closed_trades: list[TradeRecord] = []

    @property
    def active_trades(self) -> dict[str, TradeRecord]:
        """Return dict of currently open trades."""
        return self._trades

    def can_add_position(self) -> bool:
        """Check whether a new position can be added (under limit)."""
        return len(self._trades) < config.MAX_POSITIONS_OPEN

    def has_position_for_underlying(self, symbol: str) -> bool:
        """Check if there's already an open position for this underlying."""
        return any(t.symbol == symbol for t in self._trades.values())

    def add_trade(
        self,
        symbol: str,
        instrument_symbol: str,
        fill_price: float,
        quantity: int,
        trade_type: str,
        entry_date: date,
        target_delta: float = 0.0,
        **kwargs,
    ) -> TradeRecord:
        """
        Record a new filled entry.

        Args:
            symbol: Underlying equity symbol string
            instrument_symbol: Actual traded instrument symbol string
            fill_price: Fill price per unit
            quantity: Number of contracts/shares filled
            trade_type: Strategy identifier string
            entry_date: Date of entry
            target_delta: Target delta (for options)
            **kwargs: Additional fields stored on the trade record

        Returns:
            The created TradeRecord
        """
        trade = TradeRecord(
            symbol=symbol,
            instrument_symbol=instrument_symbol,
            entry_price=fill_price,
            entry_date=entry_date,
            trade_type=trade_type,
            quantity=quantity,
            total_cost=fill_price * quantity * 100,  # Options are 100-multiplier
            target_delta=target_delta,
            last_known_price=fill_price,
        )
        self._trades[instrument_symbol] = trade
        self._algo.debug(f"[POSITION] Opened {instrument_symbol} qty={quantity} @ {fill_price}")
        return trade

    def close_trade(
        self, instrument_symbol: str, exit_price: float, reason: str
    ) -> dict | None:
        """
        Record a closed position.

        Returns:
            dict with trade summary {pnl, reason, ...} or None if not found.
        """
        trade = self._trades.pop(instrument_symbol, None)
        if trade is None:
            return None

        trade.exit_price = exit_price
        trade.exit_date = self._algo.time.date()
        trade.exit_reason = reason
        trade.status = "CLOSED"

        pnl = (exit_price - trade.entry_price) * trade.quantity * 100
        self._closed_trades.append(trade)

        return {
            "symbol": trade.symbol,
            "instrument": instrument_symbol,
            "pnl": pnl,
            "reason": reason,
            "entry_price": trade.entry_price,
            "exit_price": exit_price,
            "holding_days": (trade.exit_date - trade.entry_date).days,
        }

    def check_exit_conditions(
        self, instrument_symbol: str, current_price: float, **kwargs
    ) -> tuple[bool, str]:
        """
        Evaluate exit conditions in priority order.

        TODO: Implement your exit logic. Priority ordering example:
          1. Event proximity (mandatory exit before catalyst)
          2. Stop loss
          3. Profit target
          4. Time limit
          5. Delta/Greeks threshold (for options)

        Returns:
            (should_exit: bool, reason: str)
        """
        trade = self._trades.get(instrument_symbol)
        if trade is None:
            return False, ""

        # Stop loss
        if current_price > 0 and trade.entry_price > 0:
            loss_pct = 1.0 - (current_price / trade.entry_price)
            if loss_pct >= config.STOP_LOSS_PCT:
                return True, config.EXIT_REASON_STOP_LOSS

        # Profit target
        if current_price > 0 and trade.entry_price > 0:
            gain_pct = (current_price / trade.entry_price) - 1.0
            if gain_pct >= config.PROFIT_TARGET_PCT:
                return True, config.EXIT_REASON_PROFIT_TARGET

        # Time limit
        today = self._algo.time.date()
        holding_days = (today - trade.entry_date).days
        if holding_days >= config.MAX_HOLDING_DAYS:
            return True, config.EXIT_REASON_TIME_LIMIT

        # TODO: Add additional exit conditions:
        # - Event proximity exit
        # - Delta/Greeks thresholds (for options)

        return False, ""
