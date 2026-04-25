"""
main.py — Platform Orchestrator (ONLY file importing LEAN SDK)

Responsibility:
  - Wire all handlers together
  - Implement platform lifecycle callbacks (initialize, on_data, on_order_event)
  - Schedule daily pipeline (scan → entry trigger → exit checks)
  - Handle async order events and fill reconciliation
  - Delegate ALL business logic to handlers (handlers are pure Python)

Architecture Rules:
  - No business logic here — only orchestration
  - All strategy parameters are in config.py
  - Dependency injection: each handler receives 'self' (algorithm reference)
  - Handlers are reusable and testable without LEAN SDK

TODO: Rename this class, configure dates/cash, and implement pipeline logic.
"""

from AlgorithmImports import *
from datetime import datetime, timedelta

from config import *
from handlers.universe_filter import UniverseFilter
from handlers.data_handler import DataHandler
from handlers.technical_validator import TechnicalValidator
from handlers.setup_checker import SetupChecker
from handlers.instrument_selector import InstrumentSelector
from handlers.position_manager import PositionManager
from handlers.option_analytics import OptionAnalytics

# TODO: Import additional handlers as you build them:
# from handlers.event_calendar import EventCalendar


def _parse_time(time_str: str):
    """Parse 'HH:MM' string into (hour, minute) integer tuple."""
    hour, minute = time_str.split(":")
    return int(hour), int(minute)


class StrategyAlgorithm(QCAlgorithm):
    """
    QuantConnect / LEAN Strategy Template

    TODO: Rename this class to match your strategy (e.g., MomentumBreakoutAlgorithm).
    """

    def initialize(self):
        """
        Initialize algorithm:
          - Platform setup (dates, cash, benchmark, warm-up)
          - Instantiate all handlers in dependency order
          - Schedule daily pipeline (scan → entry trigger → exit checks)
          - Initialize internal state dicts
        """
        # ---- Platform setup ----
        # TODO: Set your backtest date range and starting capital
        self.set_start_date(2020, 1, 1)
        self.set_end_date(2024, 12, 31)
        self.set_cash(100_000)
        self.set_benchmark("SPY")
        self.set_warm_up(SMA_LONG_PERIOD + 20)

        # ---- Handler instantiation (dependency order) ----
        self._universe_filter = UniverseFilter(self)
        self._data_handler = DataHandler(self)
        self._technical_validator = TechnicalValidator(self)
        self._option_analytics = OptionAnalytics(self)
        self._instrument_selector = InstrumentSelector(self)
        self._position_manager = PositionManager(self)
        self._setup_checker = SetupChecker(
            self,
            self._data_handler,
            technical_validator=self._technical_validator,
            instrument_selector=self._instrument_selector,
            option_analytics=self._option_analytics,
        )

        # TODO: Add event-driven handlers if your strategy is event-based:
        # self._event_calendar = EventCalendar(self)

        # ---- Internal state ----
        # Signals queued by Phase 1 scan, consumed by Phase 2 entry trigger
        self._pending_entry_signals = {}  # {symbol_str: signal_dict}
        # Orders awaiting fill confirmation from on_order_event()
        self._pending_orders = {}  # {order_id: order_metadata_dict}
        # Option chain subscriptions (if trading options)
        self._option_symbols = {}  # {equity_symbol_str: canonical_option_symbol}

        # ---- Data normalization (required for options compatibility) ----
        self.universe_settings.data_normalization_mode = DataNormalizationMode.RAW

        # ---- SPY subscription — anchors scheduling date/time rules ----
        spy_symbol = self.add_equity("SPY", Resolution.DAILY).symbol

        # ---- Schedule: Phase 1 — universe scan ----
        scan_hour, scan_minute = _parse_time(SCAN_SCHEDULE_TIME)
        self.schedule.on(
            self.date_rules.every_day(spy_symbol),
            self.time_rules.at(scan_hour, scan_minute),
            self._scan_universe,
        )

        # ---- Schedule: Phase 2 — entry trigger ----
        entry_hour, entry_minute = _parse_time(ENTRY_TRIGGER_TIME)
        self.schedule.on(
            self.date_rules.every_day(spy_symbol),
            self.time_rules.at(entry_hour, entry_minute),
            self._check_entry_triggers,
        )

        # ---- Schedule: Phase 3 — exit checks (multiple intraday times) ----
        for exit_time in EXIT_CHECK_TIMES:
            exit_hour, exit_minute = _parse_time(exit_time)
            self.schedule.on(
                self.date_rules.every_day(spy_symbol),
                self.time_rules.at(exit_hour, exit_minute),
                self._check_exit_conditions,
            )

        # ---- Universe selection ----
        tickers = self._universe_filter.get_universe()
        self.add_universe_selection(
            ManualUniverseSelectionModel(
                [Symbol.Create(t, SecurityType.Equity, Market.USA) for t in tickers]
            )
        )

    # ========================================================================
    # PLATFORM CALLBACKS
    # ========================================================================

    def on_data(self, slice):
        """
        Called on every data bar.

        TODO: Add logic for:
          - Caching option chains from slice.option_chains
          - Updating last_known_price for open positions
          - Any intraday signal detection
        """
        if self.is_warming_up:
            return

        # Update last_known_price for all open positions
        for instrument_symbol, trade in self._position_manager.active_trades.items():
            security = self.securities.get(instrument_symbol)
            if security is not None and security.price > 0:
                trade.last_known_price = security.price

    def on_order_event(self, order_event):
        """
        Async callback: order filled/rejected/cancelled.

        Pattern:
          - On FILLED BUY  → position_manager.add_trade()
          - On FILLED SELL → position_manager.close_trade()
        """
        if order_event.status != OrderStatus.FILLED:
            return

        order_id = order_event.order_id
        pending = self._pending_orders.pop(order_id, None)
        if pending is None:
            return

        fill_price = order_event.fill_price
        fill_qty = abs(order_event.fill_quantity)
        symbol = pending["symbol"]
        instrument = pending["instrument"]

        if pending["type"] == "entry":
            self._position_manager.add_trade(
                symbol=symbol,
                instrument_symbol=instrument,
                fill_price=fill_price,
                quantity=fill_qty,
                trade_type="SETUP",
                entry_date=self.time.date(),
                target_delta=TARGET_DELTA,
            )
            self.log(f"[ENTRY FILLED] {instrument} qty={fill_qty} @ {fill_price:.2f}")

        elif pending["type"] == "exit":
            result = self._position_manager.close_trade(
                instrument_symbol=instrument,
                exit_price=fill_price,
                reason=pending.get("reason", EXIT_REASON_MANUAL),
            )
            if result:
                self.log(
                    f"[EXIT FILLED] {instrument} qty={fill_qty} @ {fill_price:.2f} "
                    f"P&L={result.get('pnl', 0):.2f} reason={result.get('reason')}"
                )

    def on_securities_changed(self, changes):
        """
        Fires when universe composition changes.
        Override if you need to handle additions/removals.
        """
        pass

    # ========================================================================
    # DAILY PIPELINE (Scheduled Events)
    # ========================================================================

    def _scan_universe(self):
        """
        Phase 1: Universe Scan — scheduled at SCAN_SCHEDULE_TIME.

        TODO: Implement your scan logic:
          1. Reset caches
          2. Get candidates from universe filter (+ optional event filter)
          3. For each candidate: validate technicals, setup, instrument
          4. Queue passing symbols in _pending_entry_signals
        """
        if self.is_warming_up:
            return

        self._pending_entry_signals.clear()
        self._data_handler.clear_cache()

        universe = set(self._universe_filter.get_universe())
        self.debug(f"[SCAN] Universe size={len(universe)}")

        for sym_str in universe:
            try:
                security = self.securities.get(sym_str)
                if security is None or security.price <= 0:
                    continue

                current_price = security.price
                symbol = security.symbol

                indicators = self._data_handler.get_indicators(symbol)
                if not indicators:
                    continue

                # TODO: Add your validation gates here:
                # tech = self._technical_validator.validate_daily_technicals(...)
                # setup = self._setup_checker.validate_setup(...)
                # instrument = self._instrument_selector.select_instrument(...)

                # TODO: Queue passing signals:
                # self._pending_entry_signals[sym_str] = {
                #     "symbol": symbol,
                #     "instrument": instrument,
                # }

            except Exception as ex:
                self.error(f"[SCAN] Error processing {sym_str}: {ex}")

        self.debug(f"[SCAN] Done — {len(self._pending_entry_signals)} signal(s) queued")

    def _check_entry_triggers(self):
        """
        Phase 2: Entry Trigger — scheduled at ENTRY_TRIGGER_TIME.

        TODO: Implement your entry logic:
          1. For each pending signal, re-validate Phase 2 conditions
          2. Check position capacity and no duplicate underlying
          3. Place order (MarketOrder or LimitOrder)
        """
        if self.is_warming_up:
            return

        self.debug(f"[ENTRY] Checking {len(self._pending_entry_signals)} pending signal(s)")

        for sym_str, signal in list(self._pending_entry_signals.items()):
            try:
                if not self._position_manager.can_add_position():
                    self.debug(f"[ENTRY] At max capacity ({MAX_POSITIONS_OPEN}) — stopping")
                    break

                if self._position_manager.has_position_for_underlying(sym_str):
                    continue

                # TODO: Re-validate entry conditions
                # TODO: Place order and track in _pending_orders:
                # ticket = self.market_order(instrument_symbol, FIXED_CONTRACTS)
                # self._pending_orders[ticket.order_id] = {
                #     "type": "entry",
                #     "symbol": sym_str,
                #     "instrument": str(instrument_symbol),
                # }

            except Exception as ex:
                self.error(f"[ENTRY] Error processing {sym_str}: {ex}")

    def _check_exit_conditions(self):
        """
        Phase 3: Exit Check — scheduled at EXIT_CHECK_TIMES.

        TODO: Implement your exit logic:
          1. For each active position, evaluate exit conditions
          2. On exit signal, place sell order via _execute_exit()
        """
        if self.is_warming_up:
            return

        for instrument_symbol, trade in list(self._position_manager.active_trades.items()):
            try:
                current_price = trade.last_known_price

                should_exit, reason = self._position_manager.check_exit_conditions(
                    instrument_symbol, current_price
                )
                if should_exit:
                    self._execute_exit(instrument_symbol, reason)

            except Exception as ex:
                self.error(f"[EXIT CHECK] Error on {instrument_symbol}: {ex}")

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def _execute_exit(self, instrument_symbol: str, reason: str):
        """
        Place a sell order to close a position.

        Args:
            instrument_symbol: The option/equity symbol to sell
            reason: Exit reason constant from config.py
        """
        trade = self._position_manager.active_trades.get(instrument_symbol)
        if trade is None:
            return

        ticket = self.market_order(instrument_symbol, -trade.quantity)
        self._pending_orders[ticket.order_id] = {
            "type": "exit",
            "symbol": trade.symbol,
            "instrument": instrument_symbol,
            "reason": reason,
        }
        self.log(f"[EXIT ORDER] {instrument_symbol} reason={reason}")
