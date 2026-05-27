"""
main.py — Power Trend Algo 1 platform orchestrator.

This is the ONLY file that imports the LEAN SDK. All business logic lives in
pure-Python handlers under `handlers/`.

Daily lifecycle (single callback at DAILY_EVAL_TIME):
  1. Refresh QQQ indicators → regime_filter.update(...)
  2. Update risk manager with portfolio equity
  3. For each open position:
       a. exit_engine.check_partial → reduce_position if fires (skip step b)
       b. exit_engine.check_full    → close_trade if any rule fires
  4. If regime.entries_allowed() AND risk.is_new_entry_allowed():
       For each symbol in active universe (excluding QQQ):
         - if open: try add-on
         - else:    try initial (respect MAX_POSITIONS_OPEN)
  5. on_order_event → position_manager.add_leg / reduce_position / close_trade
"""

from AlgorithmImports import *

import config
from handlers.data_handler import DataHandler
from handlers.universe_filter import DynamicUniverseSelector
from handlers.regime_filter import RegimeFilter
from handlers.risk_manager import RiskManager
from handlers.position_manager import PositionManager
from handlers.pyramiding_manager import PyramidingManager
from handlers.entry_engine import EntryEngine
from handlers.exit_engine import ExitEngine
from handlers.state_store import StateStore


def _parse_time(hhmm: str):
    h, m = hhmm.split(":")
    return int(h), int(m)


class PowerTrendAlgorithm(QCAlgorithm):
    """Power Trend Algo 1 — long US equities gated by QQQ Power Trend regime."""

    # ====================================================================
    # INITIALIZE
    # ====================================================================

    def initialize(self):
        # ---- Platform setup ----
        self.set_start_date(2003, 1, 1)
        self.set_end_date(2024, 12, 31)
        self.set_cash(100_000)
        self.set_benchmark("SPY")
        # Warm-up covers SMA50 + ATR50 + 14d universe cache.
        self.set_warm_up(120)

        self.universe_settings.resolution = Resolution.DAILY
        self.universe_settings.data_normalization_mode = DataNormalizationMode.ADJUSTED

        # ---- Regime symbol (QQQ) always subscribed ----
        self._qqq_symbol = self.add_equity(
            config.REGIME_SYMBOL, Resolution.DAILY
        ).symbol

        # ---- Handlers ----
        self._data = DataHandler(self)
        self._universe = DynamicUniverseSelector(self)
        self._regime = RegimeFilter(self)
        self._risk = RiskManager(self)
        self._positions = PositionManager(self)
        self._pyramiding = PyramidingManager(self)
        self._entry = EntryEngine(self)
        self._exit = ExitEngine(self)
        self._state_store = StateStore(self)

        # ---- Dynamic universe ----
        self.add_universe(self._universe.coarse_filter)

        # ---- Pending order metadata ----
        # {order_id: {"type": "entry"|"exit"|"trim", "symbol": str, "reason": str?}}
        self._pending_orders: dict = {}
        # Current active universe (set by on_securities_changed).
        self._active_universe: set = set()

        # ---- Schedule single daily evaluation ----
        hour, minute = _parse_time(config.DAILY_EVAL_TIME)
        self.schedule.on(
            self.date_rules.every_day(self._qqq_symbol),
            self.time_rules.at(hour, minute),
            self._evaluate,
        )

        # ---- Restart rehydration (live only) ----
        if getattr(self, "live_mode", False):
            self._rehydrate_state()

    def _rehydrate_state(self) -> None:
        """Restore handler state from ObjectStore on live-node restart."""
        payload = self._state_store.load()
        if payload is None:
            self.log("[STATE] no prior snapshot found; cold start")
            return
        # Build broker_quantities map so positions the broker no longer holds
        # are dropped (the broker is the source of truth).
        broker_qty: dict = {}
        for sym in payload.get("positions", {}).keys():
            try:
                holding = self.portfolio[sym]
                broker_qty[sym] = int(holding.quantity) if holding is not None else 0
            except Exception:  # noqa: BLE001
                broker_qty[sym] = 0
        summary = self._state_store.rehydrate(
            payload,
            position_manager=self._positions,
            risk_manager=self._risk,
            regime_filter=self._regime,
            broker_quantities=broker_qty,
        )
        self.log(
            f"[STATE] rehydrated positions={summary['positions_restored']} "
            f"hwm={summary['hwm']:.2f} regime={summary['regime_state']}"
        )

    # ====================================================================
    # PLATFORM CALLBACKS
    # ====================================================================

    def on_securities_changed(self, changes):
        """Track the active universe set for entry iteration."""
        for added in changes.added_securities:
            self._active_universe.add(str(added.symbol))
        for removed in changes.removed_securities:
            self._active_universe.discard(str(removed.symbol))

    def on_order_event(self, order_event):
        """Route fills to position_manager."""
        if order_event.status != OrderStatus.FILLED:
            return

        meta = self._pending_orders.pop(order_event.order_id, None)
        if meta is None:
            return

        fill_price = float(order_event.fill_price)
        fill_qty = int(abs(order_event.fill_quantity))
        sym = meta["symbol"]
        today = self.time.date()

        otype = meta["type"]
        if otype == "entry":
            self._positions.add_leg(sym, fill_price, fill_qty, today)
            self.log(f"[FILL ENTRY] {sym} qty={fill_qty} @ {fill_price:.2f}")
        elif otype == "trim":
            self._positions.reduce_position(
                sym, fill_qty, fill_price, meta.get("reason", "TRIM")
            )
            self.log(f"[FILL TRIM] {sym} qty={fill_qty} @ {fill_price:.2f}")
        elif otype == "exit":
            self._positions.close_trade(
                sym, fill_price, meta.get("reason", "EXIT")
            )
            self.log(f"[FILL EXIT] {sym} qty={fill_qty} @ {fill_price:.2f}")

        # Persist after any position mutation so a restart sees the latest book.
        self._state_store.save(self._positions, self._risk, self._regime)

    # ====================================================================
    # DAILY EVALUATION
    # ====================================================================

    def _evaluate(self):
        if self.is_warming_up:
            return

        self._data.clear_cache()

        # ---- 1. Regime update from QQQ ----
        qqq_ind = self._data.get_indicators(self._qqq_symbol)
        self._regime.update(qqq_ind)

        # ---- 2. Risk gate update ----
        self._risk.update(float(self.portfolio.total_portfolio_value))
        drawdown_breached = not self._risk.is_new_entry_allowed() and (
            self._risk.drawdown >= config.MAX_ACCOUNT_DRAWDOWN_PCT
        )

        # ---- 3. Exit checks on open positions ----
        for sym_str in list(self._positions.active_trades.keys()):
            trade = self._positions.get_trade(sym_str)
            if trade is None:
                continue
            security = self.securities.get(sym_str)
            if security is None or security.price <= 0:
                continue
            trade.last_known_price = float(security.price)

            indicators = self._data.get_indicators(security.symbol)
            if indicators is None:
                continue

            # Priority 0 — partial trim
            trim = self._exit.check_partial(trade, indicators)
            if trim is not None:
                self._submit_trim(security.symbol, trim["quantity"], trim["reason"])
                continue  # skip full checks this bar per spec

            # Priorities 1-5 — full exit
            reason = self._exit.check_full(trade, indicators, drawdown_breached)
            if reason is not None:
                self._submit_exit(security.symbol, trade.total_quantity, reason)

        # ---- 4. Entry checks ----
        if not self._regime.entries_allowed():
            return
        if not self._risk.is_new_entry_allowed():
            return

        portfolio_value = float(self.portfolio.total_portfolio_value)
        regime_str = config.REGIME_SYMBOL

        for sym_str in list(self._active_universe):
            if sym_str == regime_str or sym_str.startswith(regime_str + " "):
                continue
            security = self.securities.get(sym_str)
            if security is None or security.price <= 0:
                continue

            indicators = self._data.get_indicators(security.symbol)
            if indicators is None:
                continue

            existing = self._positions.get_trade(sym_str)

            if existing is not None:
                # Add-on entry path.
                if not self._pyramiding.can_add(existing):
                    continue
                if not self._entry.check_addon(existing, indicators):
                    continue
                qty = self._pyramiding.compute_leg_size(
                    portfolio_value, float(security.price)
                )
                if qty <= 0:
                    continue
                self._submit_entry(security.symbol, qty)
            else:
                # Initial entry path.
                if not self._positions.can_add_position():
                    break  # capacity full — stop scanning
                if not self._entry.check_initial(indicators):
                    continue
                qty = self._pyramiding.compute_leg_size(
                    portfolio_value, float(security.price)
                )
                if qty <= 0:
                    continue
                self._submit_entry(security.symbol, qty)

        # ---- 5. Persist daily snapshot (regime counters + HWM) ----
        self._state_store.save(self._positions, self._risk, self._regime)

    # ====================================================================
    # ORDER HELPERS
    # ====================================================================

    def _submit_entry(self, symbol, quantity: int) -> None:
        ticket = self.market_order(symbol, quantity)
        self._pending_orders[ticket.order_id] = {
            "type": "entry",
            "symbol": str(symbol),
        }

    def _submit_trim(self, symbol, quantity: int, reason: str) -> None:
        ticket = self.market_order(symbol, -quantity)
        self._pending_orders[ticket.order_id] = {
            "type": "trim",
            "symbol": str(symbol),
            "reason": reason,
        }

    def _submit_exit(self, symbol, quantity: int, reason: str) -> None:
        ticket = self.market_order(symbol, -quantity)
        self._pending_orders[ticket.order_id] = {
            "type": "exit",
            "symbol": str(symbol),
            "reason": reason,
        }
