"""
handlers/state_store.py — ObjectStore-backed state persistence for live trading.

QC has no automatic state management for live algorithms. When QC restarts a
live node (deploys, crashes, maintenance), all in-memory handler state is
wiped — open broker positions remain, but the algo forgets leg history,
avg_entry_price, HWM, and regime counters. That silently breaks the
stop-loss math, pyramid caps, and the drawdown gate.

This handler serialises position/risk/regime state into ObjectStore on every
fill and at the end of each daily evaluation, then rehydrates on restart.

Pure-Python — no LEAN imports. Constructor `__init__(self, algorithm)`.

Schema is versioned. A version mismatch on load is treated as a cold start
(returns None); callers should fall back to defaults rather than partial
state.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Optional

import config

# Bump when the on-disk schema changes incompatibly.
STATE_SCHEMA_VERSION: int = 1
OBJECT_STORE_KEY: str = "power_trend/state_v1"


# ---- ISO helpers --------------------------------------------------------- #

def _iso_date(d) -> Optional[str]:
    if d is None:
        return None
    if isinstance(d, datetime):
        return d.date().isoformat()
    if isinstance(d, date):
        return d.isoformat()
    return None


def _parse_date(s: Optional[str]) -> Optional[date]:
    if s is None or s == "":
        return None
    return date.fromisoformat(s)


# ---- Serialisation ------------------------------------------------------- #

def _serialise_trade(trade) -> dict:
    return {
        "symbol": trade.symbol,
        "legs": [
            {
                "entry_date": _iso_date(leg.entry_date),
                "entry_price": float(leg.entry_price),
                "quantity": int(leg.quantity),
            }
            for leg in trade.legs
        ],
        "total_quantity": int(trade.total_quantity),
        "avg_entry_price": float(trade.avg_entry_price),
        "leg_count": int(trade.leg_count),
        "last_leg_date": _iso_date(trade.last_leg_date),
        "last_known_price": float(trade.last_known_price),
        "status": trade.status,
    }


def _serialise_positions(position_manager) -> dict:
    return {
        sym: _serialise_trade(trade)
        for sym, trade in position_manager.active_trades.items()
    }


def _serialise_risk(risk_manager) -> dict:
    return {
        "high_water_mark": float(risk_manager.high_water_mark),
        "current_equity": float(risk_manager.current_equity),
    }


def _serialise_regime(regime_filter) -> dict:
    return {
        "days_low_above_ema21": int(regime_filter.days_low_above_ema21),
        "days_ema21_above_sma50": int(regime_filter.days_ema21_above_sma50),
        "sma50_rising": bool(regime_filter.sma50_rising),
        "is_blue_bar": bool(regime_filter.is_blue_bar),
        "current_state": regime_filter.current_state,
        "last_update_date": _iso_date(regime_filter._last_update_date),
    }


def build_snapshot(position_manager, risk_manager, regime_filter, *, now=None) -> dict:
    """Build a JSON-safe snapshot dict (does not touch ObjectStore)."""
    return {
        "version": STATE_SCHEMA_VERSION,
        "saved_at": (now or datetime.now(timezone.utc)).isoformat(timespec="seconds"),
        "positions": _serialise_positions(position_manager),
        "risk": _serialise_risk(risk_manager),
        "regime": _serialise_regime(regime_filter),
    }


# ---- Rehydration -------------------------------------------------------- #

def _rehydrate_positions(position_manager, positions_payload: dict) -> None:
    """Replace position_manager.active_trades with rehydrated Trades."""
    from handlers.position_manager import Trade, TradeLeg

    trades: dict = position_manager.active_trades
    trades.clear()
    for sym, payload in positions_payload.items():
        legs = [
            TradeLeg(
                entry_date=_parse_date(leg["entry_date"]) or date.today(),
                entry_price=float(leg["entry_price"]),
                quantity=int(leg["quantity"]),
            )
            for leg in payload.get("legs", [])
        ]
        trade = Trade(
            symbol=sym,
            legs=legs,
            total_quantity=int(payload.get("total_quantity", 0)),
            avg_entry_price=float(payload.get("avg_entry_price", 0.0)),
            leg_count=int(payload.get("leg_count", len(legs))),
            last_leg_date=_parse_date(payload.get("last_leg_date")),
            last_known_price=float(payload.get("last_known_price", 0.0)),
            status=payload.get("status", "OPEN"),
        )
        # Recompute as a safety net against drift in saved totals.
        trade._recompute()
        trades[sym] = trade


def _rehydrate_risk(risk_manager, risk_payload: dict) -> None:
    risk_manager.high_water_mark = float(risk_payload.get("high_water_mark", 0.0))
    risk_manager.current_equity = float(risk_payload.get("current_equity", 0.0))


def _rehydrate_regime(regime_filter, regime_payload: dict) -> None:
    regime_filter.days_low_above_ema21 = int(
        regime_payload.get("days_low_above_ema21", 0)
    )
    regime_filter.days_ema21_above_sma50 = int(
        regime_payload.get("days_ema21_above_sma50", 0)
    )
    regime_filter.sma50_rising = bool(regime_payload.get("sma50_rising", False))
    regime_filter.is_blue_bar = bool(regime_payload.get("is_blue_bar", False))
    regime_filter.current_state = regime_payload.get(
        "current_state", config.REGIME_NO_TREND
    )
    regime_filter._last_update_date = _parse_date(
        regime_payload.get("last_update_date")
    )


# ---- Public handler ----------------------------------------------------- #

class StateStore:
    """ObjectStore-backed persistence + rehydration of handler state."""

    KEY: str = OBJECT_STORE_KEY
    VERSION: int = STATE_SCHEMA_VERSION

    def __init__(self, algorithm):
        self._algo = algorithm

    # ---- Write ----------------------------------------------------------

    def save(self, position_manager, risk_manager, regime_filter) -> None:
        """Serialise current state and write to ObjectStore."""
        store = getattr(self._algo, "object_store", None)
        if store is None:
            return
        try:
            payload = build_snapshot(position_manager, risk_manager, regime_filter)
            store.save(self.KEY, json.dumps(payload))
        except Exception as exc:  # noqa: BLE001
            # Persistence must never crash the daily evaluation.
            self._safe_log(f"[STATE] save failed: {exc!r}")

    # ---- Read -----------------------------------------------------------

    def load(self) -> Optional[dict]:
        """
        Read and parse the snapshot. Returns the payload dict on success,
        None on missing key, corrupt JSON, or version mismatch.
        """
        store = getattr(self._algo, "object_store", None)
        if store is None or not store.contains_key(self.KEY):
            return None
        try:
            raw = store.read(self.KEY)
            payload = json.loads(raw)
        except Exception as exc:  # noqa: BLE001
            self._safe_log(f"[STATE] load failed: {exc!r}")
            return None
        if not isinstance(payload, dict):
            self._safe_log("[STATE] load: payload is not a dict, cold start")
            return None
        if payload.get("version") != self.VERSION:
            self._safe_log(
                f"[STATE] version mismatch "
                f"(got {payload.get('version')!r}, want {self.VERSION}); cold start"
            )
            return None
        return payload

    def rehydrate(
        self,
        payload: dict,
        *,
        position_manager,
        risk_manager,
        regime_filter,
        broker_quantities: Optional[dict] = None,
    ) -> dict:
        """
        Apply *payload* to the three handlers. If *broker_quantities* is
        provided (mapping symbol -> int quantity from self.portfolio), any
        rehydrated trade whose broker quantity is zero is dropped — the broker
        is the source of truth for open positions.

        Returns a small summary dict for logging.
        """
        positions_payload = payload.get("positions", {})
        if broker_quantities is not None:
            positions_payload = {
                sym: t
                for sym, t in positions_payload.items()
                if int(broker_quantities.get(sym, 0)) != 0
            }
        _rehydrate_positions(position_manager, positions_payload)
        _rehydrate_risk(risk_manager, payload.get("risk", {}))
        _rehydrate_regime(regime_filter, payload.get("regime", {}))
        return {
            "positions_restored": len(positions_payload),
            "hwm": risk_manager.high_water_mark,
            "regime_state": regime_filter.current_state,
        }

    # ---- Internals ------------------------------------------------------

    def _safe_log(self, msg: str) -> None:
        log_fn = getattr(self._algo, "log", None) or getattr(self._algo, "debug", None)
        if callable(log_fn):
            log_fn(msg)
