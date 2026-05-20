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
        self.set_start_date(2021, 1, 1)
        self.set_end_date(2024, 12, 31)
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
        ticket = self.transactions.get_order_ticket(order_event.order_id)
        if ticket is None:
            return
        tag = str(ticket.tag)
        if not tag:
            return

        parts = tag.split("|", 2)
        order_type = parts[0]
        symbol = parts[1] if len(parts) > 1 else ""
        reason = parts[2] if len(parts) > 2 else ""

        fill_price = float(order_event.fill_price)
        fill_qty = abs(int(order_event.fill_quantity))

        if order_type in (EntrySignal.INITIAL, EntrySignal.ADD):
            self._positions.add_leg(
                symbol=symbol,
                fill_price=fill_price,
                quantity=fill_qty,
                fill_date=self.time.date(),
            )
            self.log(f"[FILL ENTRY/{order_type}] {symbol} qty={fill_qty} @ {fill_price:.2f}")
        elif order_type == "PARTIAL_EXIT":
            self._positions.reduce_position(symbol=symbol, qty_sold=fill_qty)
            self.log(
                f"[FILL PARTIAL EXIT] {symbol} trimmed {fill_qty} @ {fill_price:.2f} "
                f"reason={reason or config.EXIT_REASON_STRETCH_TRIM}"
            )
        elif order_type == "EXIT":
            result = self._positions.close_trade(
                symbol=symbol,
                exit_price=fill_price,
                reason=reason or config.EXIT_REASON_MANUAL,
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
        _pv = float(self.portfolio.total_portfolio_value)
        _cash = float(self.portfolio.cash)
        _leg_sz = config.INITIAL_LEG_SIZE_PCT * _pv
        self.debug(
            f"[HOLDINGS] {self.time.date()} "
            f"positions={len(self._positions.active_trades)}/{config.MAX_POSITIONS_OPEN} "
            f"cash={_cash:.0f} portfolio={_pv:.0f} leg_size={_leg_sz:.0f}"
        )

        # 2. Per-position exits
        _exited_this_bar: set = set()
        for symbol in list(self._positions.active_trades.keys()):
            trade = self._positions.get_trade(symbol)
            if trade is None:
                continue
            indicators = self._data.get_indicators(symbol)

            if not indicators:
                self.debug(
                    f"[EXIT WARN] {symbol}: no indicators — stop loss cannot evaluate, "
                    f"last_known_price={trade.last_known_price:.2f}"
                )

            # 2a. Stretch-trim partial exit (Priority 0 — fires before full-exit check)
            should_trim, trim_reason = self._exits.check_partial(trade, indicators)
            if should_trim:
                trim_qty = max(1, int(trade.total_quantity * config.PARTIAL_EXIT_TRIM_FRACTION))
                self.debug(
                    f"[TRIM SIGNAL] {symbol} reason={trim_reason} trim_qty={trim_qty} "
                    f"of total={trade.total_quantity}"
                )
                self._submit_partial_exit(symbol, trim_qty, trim_reason)
                _exited_this_bar.add(symbol)
                continue  # skip full-exit rules this bar

            # 2b. Full exit (Priorities 1-4)
            should_exit, reason = self._exits.check(trade, indicators)
            if should_exit:
                self.debug(
                    f"[EXIT SIGNAL] {symbol} reason={reason} qty={trade.total_quantity} "
                    f"avg_entry={trade.avg_entry_price:.2f}"
                )
                self._submit_exit(symbol, trade.total_quantity, reason)
                _exited_this_bar.add(symbol)

        # 3. Entries (skip if regime/risk gates closed)
        if not self._regime.entries_allowed():
            self.debug(f"[ENTRY GATE] entries blocked — regime={self._regime.current_state}")
            return
        if not self._risk.is_new_entry_allowed():
            self.debug(
                f"[ENTRY GATE] entries blocked — drawdown={self._risk.drawdown:.1%} "
                f">= {config.MAX_ACCOUNT_DRAWDOWN_PCT:.0%}"
            )
            return

        # active_trades is only updated on fill (on_order_event), so can_add_position()
        # returns stale data during this loop. _initial_pending tracks how many INITIAL
        # orders have been submitted this bar (but not yet filled) so the position cap
        # is enforced correctly without waiting for fills.
        regime_str = config.REGIME_SYMBOL
        _initial_pending = 0
        _slots_available = config.MAX_POSITIONS_OPEN - len(self._positions.active_trades)

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
            if sym_str in _exited_this_bar:
                continue

            # Gate INITIAL entries against pending-but-unfilled submissions this bar.
            # ADD signals on existing positions are still allowed past this gate.
            if signal == EntrySignal.INITIAL and _initial_pending >= _slots_available:
                continue

            portfolio_value = float(self.portfolio.total_portfolio_value)
            price = indicators["close"]
            qty = self._pyramiding.size_leg(price, portfolio_value)
            # Cap by available cash so we never submit an order we can't fill.
            available_cash = float(self.portfolio.cash)
            if available_cash < price:
                # Can't afford even 1 share — skip without penalising qty calc.
                self.debug(
                    f"[ENTRY SKIP] {sym_str}: insufficient cash ({available_cash:.0f}) "
                    f"for close={price:.2f} portfolio={portfolio_value:.0f}"
                )
                continue
            qty = min(qty, int(available_cash // price))
            if qty <= 0:
                self.debug(
                    f"[ENTRY SKIP] {sym_str}: qty=0 at close={price:.2f} "
                    f"cash={available_cash:.0f} portfolio={portfolio_value:.0f}"
                )
                continue

            self._submit_entry(symbol, sym_str, qty, signal)

            if signal == EntrySignal.INITIAL:
                _initial_pending += 1
                if _initial_pending >= _slots_available:
                    self.debug(
                        f"[ENTRY GATE] INITIAL cap reached — "
                        f"{len(self._positions.active_trades)} filled "
                        f"+ {_initial_pending} pending "
                        f"= {config.MAX_POSITIONS_OPEN}; continuing for ADD signals"
                    )

    # ------------------------------------------------------------------
    def _submit_entry(self, symbol, sym_str: str, qty: int, signal: str) -> None:
        self.market_order(symbol, qty, tag=f"{signal}|{sym_str}")

    def _submit_partial_exit(self, symbol_str: str, qty: int, reason: str) -> None:
        sec = None
        for security in self.securities.values():
            if str(security.symbol) == symbol_str:
                sec = security.symbol
                break
        if sec is None:
            # Security dropped from active universe — fall back to portfolio holdings.
            for sym in self.portfolio.keys():
                if str(sym) == symbol_str:
                    sec = sym
                    break
        if sec is None:
            self.log(
                f"[EXIT CRITICAL] {symbol_str}: not in securities or portfolio — "
                f"{qty} shares cannot be partially exited (reason={reason})"
            )
            return
        self.market_order(sec, -qty, tag=f"PARTIAL_EXIT|{symbol_str}|{reason}")

    def _submit_exit(self, symbol_str: str, qty: int, reason: str) -> None:
        sec = None
        for security in self.securities.values():
            if str(security.symbol) == symbol_str:
                sec = security.symbol
                break
        if sec is None:
            # Security dropped from active universe — fall back to portfolio holdings.
            for sym in self.portfolio.keys():
                if str(sym) == symbol_str:
                    sec = sym
                    break
        if sec is None:
            self.log(
                f"[EXIT CRITICAL] {symbol_str}: not in securities or portfolio — "
                f"{qty} shares cannot be exited (reason={reason})"
            )
            return
        self.market_order(sec, -qty, tag=f"EXIT|{symbol_str}|{reason}")
