"""
handlers/position_manager.py — Multi-Leg Option Position State

Tracks long-call positions with pyramid legs. The TradeRecord is keyed by
*underlying* symbol; individual legs may sit on different option contracts
(different expiry / strike per pyramid add).

P&L is premium-based with a contract multiplier (default 100):
    leg pnl = (exit_premium - fill_premium) * contracts * multiplier

Contract:
  add_leg(...)               Record a filled entry or pyramid add
  close_leg(...)             Close a single leg (e.g. DTE force or premium stop)
  close_trade(...)           Close all remaining legs of the trade
  active_trades              dict[underlying_str -> TradeRecord]
  can_add_position()         Under MAX_POSITIONS_OPEN limit
  has_position_for_underlying(underlying)
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import config


def _sid_for(symbol) -> Optional[str]:
    """Best-effort extraction of a stable SecurityIdentifier string from a LEAN
    Symbol. Returns None for stubs without an `.id` / `.ID` attribute.

    The SID is constant across mapfile ticker renames (e.g. BEL -> VZ both
    resolve to the same Verizon SID), so we use it as the rename-aware
    identity key alongside the human-readable ticker.
    """
    if symbol is None:
        return None
    sid_obj = getattr(symbol, "id", None) or getattr(symbol, "ID", None)
    if sid_obj is None:
        return None
    to_str = getattr(sid_obj, "to_string", None) or getattr(sid_obj, "ToString", None)
    if to_str is None:
        s = str(sid_obj)
        return s or None
    try:
        return str(to_str())
    except Exception:  # noqa: BLE001
        return None


@dataclass
class Leg:
    fill_price: float  # premium paid per share (mid at entry)
    quantity: int  # number of CONTRACTS
    fill_date: date
    contract_symbol: object = None
    expiry: Optional[date] = None
    strike: float = 0.0
    delta_at_entry: float = 0.0
    underlying_price_at_entry: float = 0.0
    status: str = "OPEN"
    exit_price: float = 0.0
    exit_date: Optional[date] = None
    exit_reason: str = ""
    pending_exit: bool = False  # True while a close order is in flight


@dataclass
class TradeRecord:
    symbol: str  # underlying ticker string (bare, e.g. "SPG")
    live_symbol: object = None  # live LEAN Symbol for history/data lookups
    legs: list = field(default_factory=list)
    last_known_price: float = 0.0
    exit_price: float = 0.0
    exit_date: Optional[date] = None
    exit_reason: str = ""
    status: str = "OPEN"

    @property
    def open_legs(self) -> list:
        return [leg for leg in self.legs if leg.status == "OPEN"]

    @property
    def total_quantity(self) -> int:
        """Total OPEN contracts across all open legs."""
        return sum(leg.quantity for leg in self.open_legs)

    @property
    def leg_count(self) -> int:
        """Total legs ever opened (used for pyramid cap)."""
        return len(self.legs)

    @property
    def avg_entry_price(self) -> float:
        """Contract-weighted average premium across OPEN legs."""
        open_legs = self.open_legs
        qty = sum(leg.quantity for leg in open_legs)
        if qty == 0:
            return 0.0
        return sum(leg.fill_price * leg.quantity for leg in open_legs) / qty

    @property
    def last_leg_date(self) -> Optional[date]:
        return self.legs[-1].fill_date if self.legs else None

    @property
    def entry_date(self) -> Optional[date]:
        return self.legs[0].fill_date if self.legs else None


class PositionManager:
    """Multi-leg long-call position tracker."""

    def __init__(self, algorithm):
        self._algo = algorithm
        self._trades: dict[str, TradeRecord] = {}
        # SID -> current ticker key. Lets us detect ticker renames where the
        # same underlying SID re-appears under a different displayed ticker.
        self._trades_by_sid: dict[str, str] = {}
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

    def has_position_for_sid(self, sid_key: Optional[str]) -> bool:
        """Return True if any open trade is keyed to the given SID (rename-safe)."""
        if not sid_key:
            return False
        return sid_key in self._trades_by_sid

    def get_trade_by_sid(self, sid_key: Optional[str]) -> Optional[TradeRecord]:
        if not sid_key:
            return None
        ticker = self._trades_by_sid.get(sid_key)
        if ticker is None:
            return None
        return self._trades.get(ticker)

    def ticker_for_sid(self, sid_key: Optional[str]) -> Optional[str]:
        if not sid_key:
            return None
        return self._trades_by_sid.get(sid_key)

    @staticmethod
    def sid_for(symbol) -> Optional[str]:
        return _sid_for(symbol)

    def get_trade(self, symbol: str) -> Optional[TradeRecord]:
        return self._trades.get(symbol)

    def find_leg_by_contract(self, contract_symbol) -> Optional[tuple]:
        """Return (underlying_str, leg) for the given open option contract, else None."""
        target = str(contract_symbol)
        for underlying, trade in self._trades.items():
            for leg in trade.legs:
                if leg.status != "OPEN":
                    continue
                if str(leg.contract_symbol) == target:
                    return underlying, leg
        return None

    # ------------------------------------------------------------------
    # Mutators
    # ------------------------------------------------------------------
    def add_leg(
        self,
        symbol: str,
        fill_price: float,
        quantity: int,
        fill_date: date,
        contract_symbol=None,
        expiry: Optional[date] = None,
        strike: float = 0.0,
        delta_at_entry: float = 0.0,
        underlying_price_at_entry: float = 0.0,
        live_symbol=None,
    ) -> TradeRecord:
        sid_key = _sid_for(live_symbol)
        trade = self._trades.get(symbol)

        # Rename detection: the same SID was previously booked under a
        # different ticker. Migrate that record to the new ticker key so we
        # don't leak an orphan slot under the stale ticker.
        if trade is None and sid_key:
            old_ticker = self._trades_by_sid.get(sid_key)
            if old_ticker is not None and old_ticker != symbol:
                migrated = self._trades.pop(old_ticker, None)
                if migrated is not None:
                    migrated.symbol = symbol
                    if live_symbol is not None:
                        migrated.live_symbol = live_symbol
                    self._trades[symbol] = migrated
                    trade = migrated
                    self._algo.debug(
                        f"[POSITION-MIGRATE] {old_ticker} -> {symbol} sid={sid_key} "
                        f"legs={migrated.leg_count}"
                    )

        if trade is None:
            trade = TradeRecord(symbol=symbol, live_symbol=live_symbol)
            self._trades[symbol] = trade
        elif live_symbol is not None:
            # Keep the freshest live Symbol reference (handles SID drift).
            trade.live_symbol = live_symbol

        if sid_key:
            self._trades_by_sid[sid_key] = symbol
        leg = Leg(
            fill_price=fill_price,
            quantity=quantity,
            fill_date=fill_date,
            contract_symbol=contract_symbol,
            expiry=expiry,
            strike=strike,
            delta_at_entry=delta_at_entry,
            underlying_price_at_entry=underlying_price_at_entry,
        )
        trade.legs.append(leg)
        trade.last_known_price = fill_price
        self._algo.debug(
            f"[POSITION] {symbol} leg {trade.leg_count} contracts={quantity} "
            f"@ premium {fill_price:.2f} strike={strike} expiry={expiry} "
            f"delta={delta_at_entry:.2f}"
        )
        return trade

    def close_leg(
        self,
        underlying: str,
        leg: "Leg",
        exit_price: float,
        reason: str,
    ) -> Optional[dict]:
        """Close a single leg. Promotes the trade to CLOSED if no open legs remain."""
        trade = self._trades.get(underlying)
        if trade is None or leg not in trade.legs or leg.status != "OPEN":
            return None
        leg.status = "CLOSED"
        leg.exit_price = exit_price
        leg.exit_date = self._algo.time.date()
        leg.exit_reason = reason
        pnl = (
            (exit_price - leg.fill_price)
            * leg.quantity
            * config.OPTION_CONTRACT_MULTIPLIER
        )
        result = {
            "symbol": underlying,
            "contract_symbol": str(leg.contract_symbol) if leg.contract_symbol else "",
            "pnl": pnl,
            "reason": reason,
            "fill_price": leg.fill_price,
            "exit_price": exit_price,
            "contracts": leg.quantity,
            "expiry": leg.expiry,
            "strike": leg.strike,
        }
        if not trade.open_legs:
            trade.status = "CLOSED"
            trade.exit_price = exit_price
            trade.exit_date = self._algo.time.date()
            trade.exit_reason = reason
            self._trades.pop(underlying, None)
            self._drop_sid_index(underlying)
            self._closed_trades.append(trade)
        return result

    def close_trade(
        self,
        symbol: str,
        exit_price: float,
        reason: str,
    ) -> Optional[dict]:
        """Close ALL remaining open legs of the trade at exit_price."""
        trade = self._trades.get(symbol)
        if trade is None:
            return None
        total_pnl = 0.0
        total_contracts = 0
        for leg in trade.open_legs:
            leg.status = "CLOSED"
            leg.exit_price = exit_price
            leg.exit_date = self._algo.time.date()
            leg.exit_reason = reason
            total_pnl += (
                (exit_price - leg.fill_price)
                * leg.quantity
                * config.OPTION_CONTRACT_MULTIPLIER
            )
            total_contracts += leg.quantity
        trade.status = "CLOSED"
        trade.exit_price = exit_price
        trade.exit_date = self._algo.time.date()
        trade.exit_reason = reason
        self._trades.pop(symbol, None)
        self._drop_sid_index(symbol)
        self._closed_trades.append(trade)
        all_legs_qty = sum(l.quantity for l in trade.legs)
        avg_premium = (
            sum(l.fill_price * l.quantity for l in trade.legs) / all_legs_qty
            if all_legs_qty > 0
            else 0.0
        )
        return {
            "symbol": symbol,
            "pnl": total_pnl,
            "reason": reason,
            "avg_entry_price": avg_premium,
            "exit_price": exit_price,
            "total_quantity": total_contracts,
            "leg_count": trade.leg_count,
            "holding_days": (
                (trade.exit_date - trade.entry_date).days if trade.entry_date else 0
            ),
        }

    # ------------------------------------------------------------------
    # Internal / housekeeping
    # ------------------------------------------------------------------
    def _drop_sid_index(self, ticker: str) -> None:
        """Remove every SID -> ticker mapping that points at *ticker*."""
        stale = [s for s, t in self._trades_by_sid.items() if t == ticker]
        for s in stale:
            self._trades_by_sid.pop(s, None)

    def evict_orphan(self, ticker: str, reason: str = "MANUAL_ORPHAN") -> Optional[TradeRecord]:
        """Pop a TradeRecord whose `open_legs` is empty (e.g. all legs were
        force-closed but the parent record never got promoted to CLOSED).
        Returns the evicted record or None."""
        trade = self._trades.get(ticker)
        if trade is None:
            return None
        if trade.open_legs:
            return None
        trade.status = "CLOSED"
        trade.exit_date = self._algo.time.date()
        trade.exit_reason = reason
        self._trades.pop(ticker, None)
        self._drop_sid_index(ticker)
        self._closed_trades.append(trade)
        self._algo.debug(f"[BOOK-CLEANUP] orphan ticker={ticker} reason={reason}")
        return trade
