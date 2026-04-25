"""
main.py — Power Trend Algo 1 orchestrator (ONLY file importing LEAN SDK).

Daily lifecycle (DAILY_EVAL_TIME, anchored on QQQ):
  1. Update QQQ regime (rolling counters, state machine)
  2. Update risk manager (HWM equity)
  3. For each open position: check exit_engine; close if rule fires
  4. If regime allows entries AND risk allows entries:
       For each universe symbol (excluding QQQ):
         - get indicators
         - entry_engine.evaluate -> INITIAL/ADD/None
         - submit market order, route fills via on_order_event
"""

from AlgorithmImports import *

import config
from handlers.universe_filter import DynamicUniverseSelector
from handlers.data_handler import DataHandler
from handlers.regime_filter import RegimeFilter
from handlers.position_manager import PositionManager
from handlers.pyramiding_manager import PyramidingManager
from handlers.entry_engine import EntryEngine, EntrySignal
from handlers.exit_engine import ExitEngine
from handlers.risk_manager import RiskManager


def _parse_time(time_str: str):
    h, m = time_str.split(":")
    return int(h), int(m)


class PowerTrendAlgorithm(QCAlgorithm):

    def initialize(self):
        # ---- Platform setup ----
        self.set_start_date(2003, 1, 1)
        self.set_end_date(2020, 12, 31)
        self.set_cash(100_000)
        self.set_benchmark("SPY")
        self.set_warm_up(config.REGIME_SMA_PERIOD + 30)

        self.universe_settings.resolution = Resolution.DAILY
        self.universe_settings.data_normalization_mode = DataNormalizationMode.ADJUSTED

        # ---- Regime symbol (always subscribed, anchors scheduling) ----
        self._regime_symbol = self.add_equity(
            config.REGIME_SYMBOL, Resolution.DAILY
        ).symbol

        # ---- Handlers ----
        self._universe = DynamicUniverseSelector(self)
        self._data = DataHandler(self)
        self._regime = RegimeFilter(self)
        self._positions = PositionManager(self)
        self._pyramiding = PyramidingManager(self)
        self._risk = RiskManager(self)
        self._entries = EntryEngine(
            self, self._regime, self._risk, self._positions, self._pyramiding
        )
        self._exits = ExitEngine(self, self._risk)

        # ---- Universe (coarse callback) ----
        self.add_universe(self._universe.select_coarse)

        # ---- Pending order tracking ----
        self._pending_orders: dict = {}  # {order_id: {symbol, type}}

        # ---- Daily evaluation schedule ----
        eval_h, eval_m = _parse_time(config.DAILY_EVAL_TIME)
        self.schedule.on(
            self.date_rules.every_day(self._regime_symbol),
            self.time_rules.at(eval_h, eval_m),
            self._evaluate,
        )

    # ------------------------------------------------------------------
    # Platform callbacks
    # ------------------------------------------------------------------
    def on_data(self, slice):
        if self.is_warming_up:
            return
        for sym, trade in self._positions.active_trades.items():
            sec = self.securities.get(sym)
            if sec is not None and sec.price > 0:
                trade.last_known_price = sec.price

    def on_order_event(self, order_event):
        if order_event.status != OrderStatus.FILLED:
            return
        meta = self._pending_orders.pop(order_event.order_id, None)
        if meta is None:
            return

        symbol = meta["symbol"]
        fill_price = float(order_event.fill_price)
        fill_qty = abs(int(order_event.fill_quantity))

        if meta["type"] in (EntrySignal.INITIAL, EntrySignal.ADD):
            self._positions.add_leg(
                symbol=symbol,
                fill_price=fill_price,
                quantity=fill_qty,
                fill_date=self.time.date(),
            )
            self.log(
                f"[FILL ENTRY/{meta['type']}] {symbol} qty={fill_qty} @ {fill_price:.2f}"
            )
        elif meta["type"] == "EXIT":
            result = self._positions.close_trade(
                symbol=symbol,
                exit_price=fill_price,
                reason=meta.get("reason", config.EXIT_REASON_MANUAL),
            )
            if result:
                self.log(
                    f"[FILL EXIT] {symbol} qty={fill_qty} @ {fill_price:.2f} "
                    f"P&L={result['pnl']:.2f} reason={result['reason']}"
                )

    # ------------------------------------------------------------------
    # Daily evaluation
    # ------------------------------------------------------------------
    def _evaluate(self):
        if self.is_warming_up:
            return

        self._data.clear_cache()
        self._risk.update(float(self.portfolio.total_portfolio_value))

        # 1. Refresh QQQ regime
        qqq_indicators = self._data.get_indicators(self._regime_symbol)
        if qqq_indicators:
            self._regime.update(qqq_indicators)
        self.debug(
            f"[REGIME] {self.time.date()} state={self._regime.current_state} "
            f"low_above={self._regime.days_low_above_ema21} "
            f"ema_above={self._regime.days_ema21_above_sma50}"
        )

        # 2. Per-position exits
        for symbol in list(self._positions.active_trades.keys()):
            trade = self._positions.get_trade(symbol)
            if trade is None:
                continue
            indicators = self._data.get_indicators(symbol)
            should_exit, reason = self._exits.check(trade, indicators)
            if should_exit:
                self._submit_exit(symbol, trade.total_quantity, reason)

        # 3. Entries (skip if regime/risk gates closed)
        if not self._regime.entries_allowed():
            return
        if not self._risk.is_new_entry_allowed():
            return

        portfolio_value = float(self.portfolio.total_portfolio_value)
        regime_str = config.REGIME_SYMBOL

        for symbol in list(self._universe.active_symbols):
            sym_str = str(symbol)
            if sym_str.split()[0].upper() == regime_str:
                continue

            sec = self.securities.get(symbol)
            if sec is None or sec.price <= 0:
                continue

            indicators = self._data.get_indicators(symbol)
            if not indicators:
                continue

            signal = self._entries.evaluate(sym_str, indicators)
            if signal is None:
                continue

            qty = self._pyramiding.size_leg(indicators["close"], portfolio_value)
            if qty <= 0:
                continue

            self._submit_entry(symbol, sym_str, qty, signal)

            if not self._positions.can_add_position():
                break

    # ------------------------------------------------------------------
    def _submit_entry(self, symbol, sym_str: str, qty: int, signal: str) -> None:
        ticket = self.market_order(symbol, qty)
        if ticket is None:
            return
        self._pending_orders[ticket.order_id] = {
            "symbol": sym_str,
            "type": signal,
        }

    def _submit_exit(self, symbol_str: str, qty: int, reason: str) -> None:
        sec = None
        for s in self.securities.keys:
            if str(s) == symbol_str:
                sec = s
                break
        if sec is None:
            return
        ticket = self.market_order(sec, -qty)
        if ticket is None:
            return
        self._pending_orders[ticket.order_id] = {
            "symbol": symbol_str,
            "type": "EXIT",
            "reason": reason,
        }
