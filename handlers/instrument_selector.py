"""
handlers/instrument_selector.py — Long-dated call contract picker.

Selects a single option contract from an iterable chain for a given underlying.
Pure-logic; no LEAN imports.

Selection pipeline:
  1. Calls only (Right == "Call" / "C")
  2. DTE in [OPTION_DTE_MIN, OPTION_DTE_MAX]
  3. Delta in [OPTION_DELTA_MIN, OPTION_DELTA_MAX]
  4. OpenInterest >= OPTION_MIN_OPEN_INTEREST
  5. Bid/ask spread sanity: (ask - bid) / mid <= OPTION_MAX_BID_ASK_SPREAD_PCT
     (skipped when bid/ask are not both > 0)
  6. Rank by abs(delta - OPTION_TARGET_DELTA), tie-break by closer-to-mid DTE,
     then by tighter spread.

The picked contract is returned as a ContractRecord; main.py is responsible
for translating that into an order on the LEAN platform.
"""

from dataclasses import dataclass
from datetime import date as _date, datetime
from typing import Iterable, Optional

import config


@dataclass
class ContractRecord:
    contract_symbol: object  # opaque (LEAN Symbol or test stub)
    underlying_symbol: str
    expiry: _date
    strike: float
    delta: float
    bid: float
    ask: float
    mid_price: float
    open_interest: int


class InstrumentSelector:
    """Pick a single long-dated call from an option chain."""

    def __init__(self, algorithm):
        self._algo = algorithm

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def select(
        self,
        underlying_symbol: str,
        chain: Iterable,
        today: Optional[_date] = None,
    ) -> Optional[ContractRecord]:
        """Return the best ContractRecord, or None if nothing qualifies."""
        if chain is None:
            return None
        if today is None:
            today = self._algo.time.date()

        target = config.OPTION_TARGET_DELTA
        mid_dte = (config.OPTION_DTE_MIN + config.OPTION_DTE_MAX) // 2

        candidates: list[tuple[float, float, float, ContractRecord]] = []
        for contract in chain:
            record = self._evaluate_contract(contract, underlying_symbol, today)
            if record is None:
                continue
            delta_dist = abs(record.delta - target)
            dte_dist = abs(self._days_to_expiry(record.expiry, today) - mid_dte)
            spread = max(record.ask - record.bid, 0.0)
            candidates.append((delta_dist, dte_dist, spread, record))

        if not candidates:
            return None

        candidates.sort(key=lambda t: (t[0], t[1], t[2]))
        return candidates[0][3]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _evaluate_contract(
        self, contract, underlying_symbol: str, today: _date
    ) -> Optional[ContractRecord]:
        right = self._right(contract)
        if right not in ("call", "c"):
            return None

        expiry = self._expiry(contract)
        if expiry is None:
            return None
        dte = self._days_to_expiry(expiry, today)
        if dte < config.OPTION_DTE_MIN or dte > config.OPTION_DTE_MAX:
            return None

        delta = self._delta(contract)
        if delta is None:
            return None
        if delta < config.OPTION_DELTA_MIN or delta > config.OPTION_DELTA_MAX:
            return None

        oi = self._open_interest(contract)
        if oi < config.OPTION_MIN_OPEN_INTEREST:
            return None

        bid = float(getattr(contract, "BidPrice", getattr(contract, "bid", 0.0)) or 0.0)
        ask = float(getattr(contract, "AskPrice", getattr(contract, "ask", 0.0)) or 0.0)
        mid = (bid + ask) / 2.0 if (bid > 0 and ask > 0) else 0.0
        if bid > 0 and ask > 0 and mid > 0:
            spread_pct = (ask - bid) / mid
            if spread_pct > config.OPTION_MAX_BID_ASK_SPREAD_PCT:
                return None
        if mid <= 0:
            # Fall back to last price if mid unavailable
            last = float(getattr(contract, "LastPrice", getattr(contract, "price", 0.0)) or 0.0)
            if last <= 0:
                return None
            mid = last

        strike = float(getattr(contract, "Strike", getattr(contract, "strike", 0.0)) or 0.0)
        contract_symbol = getattr(contract, "Symbol", getattr(contract, "symbol", contract))

        return ContractRecord(
            contract_symbol=contract_symbol,
            underlying_symbol=underlying_symbol,
            expiry=expiry,
            strike=strike,
            delta=delta,
            bid=bid,
            ask=ask,
            mid_price=mid,
            open_interest=int(oi),
        )

    @staticmethod
    def _right(contract) -> str:
        right = getattr(contract, "Right", getattr(contract, "right", ""))
        return str(right).strip().lower() if right is not None else ""

    @staticmethod
    def _expiry(contract) -> Optional[_date]:
        expiry = getattr(contract, "Expiry", getattr(contract, "expiry", None))
        if expiry is None:
            return None
        if isinstance(expiry, datetime):
            return expiry.date()
        return expiry

    @staticmethod
    def _days_to_expiry(expiry: _date, today: _date) -> int:
        return (expiry - today).days

    @staticmethod
    def _delta(contract) -> Optional[float]:
        greeks = getattr(contract, "Greeks", None) or getattr(contract, "greeks", None)
        delta = None
        if greeks is not None:
            delta = getattr(greeks, "Delta", None)
            if delta is None:
                delta = getattr(greeks, "delta", None)
        if delta is None:
            delta = getattr(contract, "delta", None)
        if delta is None:
            return None
        try:
            return abs(float(delta))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _open_interest(contract) -> int:
        oi = getattr(contract, "OpenInterest", None)
        if oi is None:
            oi = getattr(contract, "open_interest", 0)
        try:
            return int(oi or 0)
        except (TypeError, ValueError):
            return 0
