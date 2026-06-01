"""
main.py — Power Trend Algo 1 (QuantConnect entry point)

This is the ONLY file that imports the LEAN SDK. All trading logic lives
in pure-Python handlers under handlers/.

Daily lifecycle (single _evaluate() callback at DAILY_EVAL_TIME):

    1. risk_manager.update()             update HWM
    2. data_handler.clear_cache()        new bar -> new cache
    3. regime_filter.update(QQQ_ind)     advance Power Trend state
    4. exit_engine.generate_exits()      apply partial + full exits
    5. entry_engine.generate_entries()   initial + add-on
    6. on_order_event()                  record fills, update position_manager
"""

from AlgorithmImports import *

import config
from handlers.data_handler import DataHandler
from handlers.entry_engine import EntryEngine
from handlers.exit_engine import ExitEngine
from handlers.position_manager import PositionManager
from handlers.pyramiding_manager import PyramidingManager
from handlers.regime_filter import RegimeFilter
from handlers.risk_manager import RiskManager
from handlers.universe_filter import DynamicUniverseSelector


class PowerTrendAlgo(QCAlgorithm):
    # ==================================================================
    # Initialisation
    # ==================================================================
    def initialize(self):
        # self.set_start_date(2022, 1, 1)
        # self.set_cash(12000)

        # Live trading settings 
        self.set_end_date(datetime.now())
        self.set_start_date(self.end_date - timedelta(5*365))
        self.set_time_zone(TimeZones.UTC)

        self.set_cash(10_000)
        
        self.set_warm_up(1, Resolution.DAILY)

        # Daily resolution: we trade once per day after the open.
        self.universe_settings.resolution = Resolution.DAILY

        # Regime symbol — always subscribed.
        self._regime_symbol = self.add_equity(
            config.REGIME_SYMBOL, Resolution.DAILY
        ).symbol

        # Dynamic universe.
        self._universe = DynamicUniverseSelector(self)
        self.add_universe(self._universe.coarse_filter)

        # Handlers.
        self._data = DataHandler(self)
        self._positions = PositionManager(self)
        self._regime = RegimeFilter(self)
        self._risk = RiskManager(self)
        self._pyramid = PyramidingManager(self)
        self._entries = EntryEngine(
            self, self._positions, self._regime, self._risk,
            self._pyramid, self._data,
        )
        self._exits = ExitEngine(
            self, self._positions, self._risk, self._data
        )

        # Map order_id -> intent so on_order_event can update state.
        self._pending_orders: dict[int, dict] = {}

        # Warm up enough for all indicators.
        warmup_days = max(
            config.STOCK_SMA_PERIOD,
            config.WEBBY_RSI_ATR_PERIOD,
            config.SMA_SLOPE_LOOKBACK + config.STOCK_SMA_PERIOD,
        ) + 10
        self.set_warm_up(warmup_days, Resolution.DAILY)

        # Schedule single daily evaluation pass.
        hh, mm = (int(x) for x in config.DAILY_EVAL_TIME.split(":"))
        self.schedule.on(
            self.date_rules.every_day(self._regime_symbol),
            self.time_rules.at(hh, mm),
            self._evaluate,
        )

        self.log(
            f"[INIT] PowerTrendAlgo ready. universe_top_n={config.UNIVERSE_TOP_N} "
            f"daily_eval={config.DAILY_EVAL_TIME}"
        )

    # ==================================================================
    # Post-warm-up hook — prime regime streak counters
    # ==================================================================
    def on_warmup_finished(self):
        """
        Replay the last N QQQ bars through RegimeFilter so the streak
        counters (_days_low_above_ema21, _days_ema21_above_sma50) reflect
        real history rather than starting at zero on the first live bar.
        Without this, activation requires 10 consecutive live bars (≈2 weeks)
        even when QQQ has been trending for months.
        """
        from handlers.data_handler import _ema, _sma, DataHandler, _MIN_HISTORY

        replay_days = max(config.LOW_ABOVE_EMA_DAYS, config.EMA_ABOVE_SMA_DAYS) + 5
        total_needed = _MIN_HISTORY + replay_days

        try:
            bars = self.history(self._regime_symbol, total_needed, Resolution.DAILY)
        except Exception:
            bars = None

        if bars is None or len(bars) < config.REGIME_SMA_PERIOD + replay_days:
            self.log("[WARMUP] Insufficient QQQ history to prime regime streaks — starting cold")
            return

        opens, highs, lows, closes, volumes = DataHandler._extract_ohlcv(bars)
        if closes is None or len(closes) < config.REGIME_SMA_PERIOD + replay_days:
            self.log("[WARMUP] OHLCV extraction failed — starting cold")
            return

        n = len(closes)
        for i in range(n - replay_days, n):
            c = closes[:i + 1]
            l = lows[:i + 1]

            ema21 = _ema(c, config.REGIME_EMA_PERIOD)
            sma50 = _sma(c, config.REGIME_SMA_PERIOD)
            if ema21 is None or sma50 is None:
                continue

            lookback = config.SMA_SLOPE_LOOKBACK
            sma50_n_ago = (
                _sma(c[: len(c) - lookback], config.REGIME_SMA_PERIOD)
                if len(c) > lookback + config.REGIME_SMA_PERIOD
                else sma50
            )

            self._regime.update({
                "low": float(l[-1]),
                "close": float(c[-1]),
                "prior_close": float(c[-2]) if len(c) >= 2 else float(c[-1]),
                "ema21": float(ema21),
                "sma50": float(sma50),
                "sma50_n_days_ago": float(sma50_n_ago if sma50_n_ago is not None else sma50),
            })

        self.log(
            f"[WARMUP] Regime primed over {replay_days} bars: "
            f"state={self._regime.current_state} "
            f"low_above_ema21={self._regime._days_low_above_ema21}d "
            f"ema21_above_sma50={self._regime._days_ema21_above_sma50}d"
        )

    # ==================================================================
    # Daily evaluation
    # ==================================================================
    def _evaluate(self):
        if self.is_warming_up:
            return

        # 1. Risk: refresh HWM
        self._risk.update()

        # 2. Indicator cache: clear so each symbol recomputes once today.
        self._data.clear_cache()

        # 3. Regime update on QQQ.
        regime_ind = self._data.get_indicators(self._regime_symbol)
        regime_state = self._regime.update(regime_ind)
        self.debug(
            f"[EVAL {self.time.date().isoformat()}] regime={regime_state} "
            f"hwm={self._risk.hwm:.0f} dd={self._risk.current_drawdown:.2%}"
        )

        # 4. Exits (partial + full).
        for decision in self._exits.generate_exits():
            self._execute_exit(decision)

        # 5. Entries (only on universe symbols that have data).
        universe = self._universe.current_universe or list(self.securities.keys())
        for decision in self._entries.generate_entries(universe):
            self._execute_entry(decision)

    # ==================================================================
    # Order execution helpers
    # ==================================================================
    def _execute_entry(self, decision):
        if decision.target_quantity <= 0:
            return
        ticket = self.market_order(decision.symbol, decision.target_quantity)
        self._pending_orders[ticket.order_id] = {
            "type": "entry",
            "kind": decision.kind,
            "symbol": decision.symbol,
            "quantity": decision.target_quantity,
        }
        self.log(
            f"[ORDER ENTRY {decision.kind}] {decision.symbol} "
            f"qty={decision.target_quantity}"
        )

    def _execute_exit(self, decision):
        if decision.quantity <= 0:
            return
        ticket = self.market_order(decision.symbol, -decision.quantity)
        self._pending_orders[ticket.order_id] = {
            "type": "exit",
            "kind": decision.kind,
            "symbol": decision.symbol,
            "quantity": decision.quantity,
            "reason": decision.reason,
        }
        self.log(
            f"[ORDER EXIT {decision.kind}] {decision.symbol} "
            f"qty={decision.quantity} reason={decision.reason}"
        )

    # ==================================================================
    # Fill handling
    # ==================================================================
    def on_order_event(self, order_event: OrderEvent):
        # QC Python enum is PascalCase (`OrderStatus.Filled`); the test stub
        # uses UPPER_CASE (`OrderStatus.FILLED`). Resolve both safely so the
        # handler doesn't silently no-op in either environment. (Symptom of
        # mismatch: zero `[POSITION] OPEN` log lines despite `[ORDER ENTRY]`
        # lines firing — see debugging/SKILL.md.)
        status_name = getattr(order_event.status, "name", str(order_event.status))
        if status_name.lower() != "filled":
            return

        intent = self._pending_orders.pop(order_event.order_id, None)
        if intent is None:
            # A fill arrived for an order we didn't queue (e.g. QC auto-
            # liquidation on universe removal). Record it so the symptom is
            # visible instead of silent.
            self.debug(
                f"[FILL UNTRACKED] order_id={order_event.order_id} "
                f"symbol={order_event.symbol} qty={order_event.fill_quantity} "
                f"price={order_event.fill_price}"
            )
            return

        symbol = intent["symbol"]
        fill_price = float(order_event.fill_price)
        fill_qty = int(abs(order_event.fill_quantity))
        today = self.time.date()

        try:
            if intent["type"] == "entry":
                if intent["kind"] == "INITIAL":
                    self._positions.open_position(
                        symbol, fill_price, fill_qty, today
                    )
                else:  # ADD_ON
                    self._positions.add_leg(
                        symbol, fill_price, fill_qty, today
                    )
            else:  # exit
                if intent["kind"] == "FULL":
                    self._positions.close_position(
                        symbol, fill_price, intent["reason"]
                    )
                    # Release universe retention so it can drop out naturally.
                    self._universe.release_symbol(symbol)
                else:  # PARTIAL
                    self._positions.reduce_position(
                        symbol, fill_qty, fill_price, intent["reason"]
                    )
        except Exception as ex:
            self.error(f"[FILL] {symbol} {intent}: {ex}")

    # ==================================================================
    # Universe lifecycle
    # ==================================================================
    def on_securities_changed(self, changes):
        """
        Prevent QC's default liquidate-on-removal behavior from bypassing
        ExitEngine. If a security currently held leaves the universe (e.g. it
        drops out of the top-450 on a refresh), we let our own exit rules
        manage the exit; QC's auto-liquidation is suppressed by force-keeping
        the symbol in the cached universe.
        """
        for removed in getattr(changes, "removed_securities", []) or []:
            sym = getattr(removed, "symbol", removed)
            if self._positions.has_position(sym):
                self._universe.retain_symbol(sym)
                self.debug(
                    f"[UNIVERSE] Retaining {sym} (open position) after removal"
                )
