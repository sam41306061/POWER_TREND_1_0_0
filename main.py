"""
main.py — Power Trend Algo 1 orchestrator (ONLY file importing LEAN SDK).

Trades long-dated CALL options on the underlying equities that pass the
Power Trend filter. Signals stay equity-driven; orders are option contracts.

Daily lifecycle (DAILY_EVAL_TIME, anchored on QQQ):
  1. Update QQQ regime (rolling counters, state machine)
  2. Update risk manager (HWM equity)
  3. For each open trade: check exit_engine -> per-leg or trade-wide exits
  4. If regime AND risk allow:
       For each universe symbol (excluding QQQ):
         - get indicators
         - entry_engine.evaluate -> INITIAL/ADD/None
         - lazily subscribe to the option chain for that underlying
         - queue a pending entry; on_data picks the contract from the chain
           and submits a market order on the option contract
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
from handlers.instrument_selector import InstrumentSelector


def _parse_time(time_str: str):
    h, m = time_str.split(":")
    return int(h), int(m)


class PowerTrendAlgorithm(QCAlgorithm):

    def initialize(self):
        # ---- Platform setup ----
        # Options data starts in Jan 2012 on QC; restrict the backtest to the
        # window where both equities AND options data are present.
        self.set_start_date(2024, 1, 1)
        self.set_end_date(2025, 12, 31)
        self.set_cash(100_000)
        self.set_benchmark("SPY")
        self.set_warm_up(config.REGIME_SMA_PERIOD + 30)

        self.universe_settings.resolution = Resolution.DAILY
        # RAW normalization is required so that strike prices and underlying
        # prices remain comparable for option chain selection.
        self.universe_settings.data_normalization_mode = DataNormalizationMode.RAW

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
        self._selector = InstrumentSelector(self)

        # ---- Universe (coarse callback) ----
        self.add_universe(self._universe.select_coarse)

        # ---- Pending state ----
        # _pending_orders: order_id -> {underlying, type, contract_symbol, ...}
        self._pending_orders: dict = {}
        # _pending_entries: list of {underlying_str, signal, queued_date}
        self._pending_entries: list = []
        # Underlyings with an entry queued OR submitted but not yet resolved.
        # Prevents duplicate INITIAL/ADD signals while a fill is in flight
        # (DAILY-resolution market orders convert to MOO and fill next day).
        # Tracks both the bare ticker (display) and the underlying SID (rename-
        # safe) so a mid-flight ticker rename can't sneak a duplicate signal in.
        self._pending_entry_underlyings: set = set()
        self._pending_entry_sids: set = set()
        # Bare-ticker -> date queued, used for TTL eviction of leaked keys.
        self._pending_entry_first_seen: dict = {}
        # Estimated cash committed to in-flight entry orders not yet filled,
        # so we don't over-commit while DAILY MOO orders are pending.
        self._reserved_cash: float = 0.0
        # Day-over-day book size tracking for [BOOK-HEALTH] delta.
        self._prev_trade_count: int = 0
        # Rolling-window throttle on new INITIAL entries. Stores fill_dates
        # of recently-queued INITIAL signals; pruned to the trailing 7 calendar
        # days each evaluation.
        self._initial_entry_history: list = []
        # _subscribed_options: SID-string -> option canonical Symbol.
        # SID-keyed (not bare-ticker) so a mapfile rename (BEL -> VZ) reuses
        # the existing chain subscription instead of creating a duplicate
        # under the new ticker.
        self._subscribed_options: dict = {}

        # ---- Daily evaluation schedule ----
        eval_h, eval_m = _parse_time(config.DAILY_EVAL_TIME)
        self.schedule.on(
            self.date_rules.every_day(self._regime_symbol),
            self.time_rules.at(eval_h, eval_m),
            self._evaluate,
        )

    # ------------------------------------------------------------------
    # Underlying-key normalization
    # ------------------------------------------------------------------
    @staticmethod
    def _underlying_key(symbol) -> str:
        """Canonical position-book key for an underlying. Returns the bare ticker
        (uppercase) so that the same equity is always one trade regardless of
        whether QC hands us a Symbol with or without the SecurityIdentifier
        suffix (e.g. 'SPG R735QTJ8XC9X' vs 'SPG')."""
        return str(symbol).split()[0].upper()

    @staticmethod
    def _sid_key(symbol):
        """Stable SecurityIdentifier string for a Symbol; None if unavailable.
        Used as the rename-aware identity key for option subscriptions and
        in-flight entry tracking."""
        if symbol is None:
            return None
        sid_obj = getattr(symbol, "id", None) or getattr(symbol, "ID", None)
        if sid_obj is None:
            return None
        to_str = getattr(sid_obj, "to_string", None) or getattr(sid_obj, "ToString", None)
        try:
            return str(to_str()) if to_str is not None else (str(sid_obj) or None)
        except Exception:  # noqa: BLE001
            return None

    # ------------------------------------------------------------------
    # Platform callbacks
    # ------------------------------------------------------------------
    def on_data(self, slice):
        if self.is_warming_up:
            return

        # Refresh last-known prices for open trades from the underlying market data.
        for key, trade in self._positions.active_trades.items():
            sec = None
            if trade.live_symbol is not None:
                sec = self.securities.get(trade.live_symbol)
            if sec is not None and sec.price > 0:
                trade.last_known_price = sec.price

        # Process any queued option entries against today's chain snapshot.
        if self._pending_entries:
            self._process_pending_entries(slice)

    def on_securities_changed(self, changes) -> None:
        """Drop option subscriptions for underlyings that left the universe and
        have no open trade (lazy unload to keep the chain footprint small)."""
        try:
            removed = list(changes.removed_securities)
        except Exception:  # noqa: BLE001 — defensive in case API differs
            return
        for sec in removed:
            key = self._underlying_key(sec.symbol)
            sid = self._sid_key(sec.symbol)
            if key == config.REGIME_SYMBOL:
                continue
            # SID-aware: keep the subscription if any open trade matches the
            # SID, even if the displayed ticker differs (mapfile rename).
            if self._positions.has_position_for_sid(sid):
                continue
            if key in self._positions.active_trades:
                continue
            opt_symbol = None
            if sid is not None:
                opt_symbol = self._subscribed_options.pop(sid, None)
            if opt_symbol is not None:
                try:
                    self.remove_security(opt_symbol)
                except Exception:  # noqa: BLE001
                    pass

    def on_order_event(self, order_event):
        status = order_event.status
        oid = order_event.order_id
        # Raw tap: prove every event reaches us and which key we're popping with.
        try:
            sym_dbg = str(order_event.symbol)
        except Exception:  # noqa: BLE001
            sym_dbg = "?"
        in_pending = oid in self._pending_orders
        self.debug(
            f"[ORDER-EVT] oid={oid} status={status} sym={sym_dbg} "
            f"in_pending={in_pending} fill_qty={getattr(order_event, 'fill_quantity', '?')} "
            f"fill_px={getattr(order_event, 'fill_price', '?')}"
        )
        terminal = (
            OrderStatus.FILLED,
            OrderStatus.INVALID,
            OrderStatus.CANCELED,
        )
        if status not in terminal:
            return
        meta = self._pending_orders.pop(oid, None)
        if meta is None:
            # Fallback: events may have fired synchronously inside market_order
            # before we registered meta (handled inline by _apply_terminal_inline),
            # OR LEAN itself issued the order (margin call / liquidation). If a
            # contract symbol matches an open leg, reconcile the book by closing
            # that leg so our state doesn't drift from the brokerage's.
            try:
                hit = self._positions.find_leg_by_contract(order_event.symbol)
            except Exception:  # noqa: BLE001
                hit = None
            if hit is not None and status == OrderStatus.FILLED:
                underlying_str, orphan_leg = hit
                orphan_leg.pending_exit = False
                fill_price = float(order_event.fill_price)
                # Use the intended exit reason stashed on the leg by
                # _submit_leg_exit; fall back to MANUAL if unset (e.g. an
                # actual broker-side margin call).
                reason = orphan_leg.exit_reason or config.EXIT_REASON_MANUAL
                self._positions.close_leg(
                    underlying_str,
                    orphan_leg,
                    fill_price,
                    reason,
                )
                self.log(
                    f"[FILL EXIT-RECONCILE] {underlying_str} oid={oid} "
                    f"contract={sym_dbg} @ {fill_price:.2f} reason={reason}"
                )
                return
            self.debug(f"[ORDER-EVT no-meta] oid={oid} status={status} sym={sym_dbg}")
            return

        underlying = meta["underlying"]

        # Non-fill terminal status: clean up pending flags so we can retry next eval.
        if status != OrderStatus.FILLED:
            if meta["type"] in (EntrySignal.INITIAL, EntrySignal.ADD):
                self._discard_pending_entry(meta["underlying"], meta.get("sid"))
                self._reserved_cash = max(
                    0.0, self._reserved_cash - float(meta.get("reserved_cost", 0.0))
                )
            elif meta["type"] in ("EXIT_LEG", "EXIT_TRADE"):
                leg = meta.get("leg")
                if leg is not None:
                    leg.pending_exit = False
            return

        fill_price = float(order_event.fill_price)
        fill_qty = abs(int(order_event.fill_quantity))

        if meta["type"] in (EntrySignal.INITIAL, EntrySignal.ADD):
            self._discard_pending_entry(meta["underlying"], meta.get("sid"))
            self._reserved_cash = max(
                0.0, self._reserved_cash - float(meta.get("reserved_cost", 0.0))
            )
            self._positions.add_leg(
                symbol=underlying,
                fill_price=fill_price,
                quantity=fill_qty,
                fill_date=self.time.date(),
                contract_symbol=meta.get("contract_symbol"),
                expiry=meta.get("expiry"),
                strike=meta.get("strike", 0.0),
                delta_at_entry=meta.get("delta", 0.0),
                underlying_price_at_entry=meta.get("underlying_price", 0.0),
                live_symbol=meta.get("live_symbol"),
            )
            self.log(
                f"[FILL ENTRY/{meta['type']}] {underlying} "
                f"contract={meta.get('contract_symbol')} contracts={fill_qty} "
                f"@ premium {fill_price:.2f}"
            )
        elif meta["type"] == "EXIT_LEG":
            trade = self._positions.get_trade(underlying)
            leg = meta.get("leg")
            if leg is not None:
                leg.pending_exit = False
            if trade is not None and leg is not None:
                result = self._positions.close_leg(
                    underlying, leg, fill_price, meta.get("reason", config.EXIT_REASON_MANUAL)
                )
                if result:
                    self.log(
                        f"[FILL EXIT-LEG] {underlying} contracts={fill_qty} "
                        f"@ {fill_price:.2f} P&L={result['pnl']:.2f} "
                        f"reason={result['reason']}"
                    )
        elif meta["type"] == "EXIT_TRADE":
            # Trade-wide exit: each leg fires its own order; close the matching leg.
            leg = meta.get("leg")
            if leg is not None:
                leg.pending_exit = False
                self._positions.close_leg(
                    underlying, leg, fill_price, meta.get("reason", config.EXIT_REASON_MANUAL)
                )
            self.log(
                f"[FILL EXIT-TRADE] {underlying} contracts={fill_qty} "
                f"@ {fill_price:.2f} reason={meta.get('reason')}"
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

        # 2. Per-trade exit checks
        for key in list(self._positions.active_trades.keys()):
            trade = self._positions.get_trade(key)
            if trade is None:
                continue
            # Use the LIVE Symbol (not the bare ticker key) for indicator
            # lookup; history(symbol) needs a real Symbol to resolve data.
            data_handle = trade.live_symbol if trade.live_symbol is not None else key
            indicators = self._data.get_indicators(data_handle)
            decisions = self._exits.check(
                trade,
                indicators,
                today=self.time.date(),
                premium_lookup=self._option_mid,
            )
            self._apply_exit_decisions(key, trade, decisions)

        # 2b. Orphan sweep — evict TradeRecords whose legs were all closed but
        # which never got promoted to CLOSED (e.g. exits arriving via the
        # reconcile path on a stale ticker key). Without this, orphan slots
        # consume the MAX_POSITIONS_OPEN cap forever.
        for key in list(self._positions.active_trades.keys()):
            trade = self._positions.get_trade(key)
            if trade is None:
                continue
            if not trade.open_legs:
                self._positions.evict_orphan(key, reason="MANUAL_ORPHAN")

        # 2c. TTL sweep on _pending_entry_underlyings: any key that's been
        # tracked for > PENDING_ENTRY_TTL_DAYS without an in-flight order
        # is leaked state — discard so the underlying isn't blocked forever.
        self._sweep_stale_pending_entries()

        # 3. Entries (regime gate only — drawdown gate disabled)
        if not self._regime.entries_allowed():
            return

        # Prune throttle history to the trailing 7 calendar days.
        today = self.time.date()
        self._initial_entry_history = [
            d for d in self._initial_entry_history if (today - d).days < 7
        ]

        regime_str = config.REGIME_SYMBOL
        signals_fired = 0
        skipped_pending = 0
        skipped_full = 0
        skipped_throttle = 0

        # Projected open count = filled positions + queued/in-flight INITIAL
        # entries whose ticker isn't already in the position book.
        # Recompute fresh each evaluation so we never queue past the cap.
        active_keys = set(self._positions.active_trades.keys())
        projected_open = len(active_keys) + sum(
            1 for k in self._pending_entry_underlyings if k not in active_keys
        )

        for symbol in list(self._universe.active_symbols):
            key = self._underlying_key(symbol)
            if key == regime_str:
                continue

            sec = self.securities.get(symbol)
            if sec is None or sec.price <= 0:
                continue

            indicators = self._data.get_indicators(symbol)
            if not indicators:
                continue

            sid = self._sid_key(symbol)

            # Skip if we already have an entry queued or in flight for this
            # name — either by displayed ticker (current) or by SID (rename-safe).
            if key in self._pending_entry_underlyings or (
                sid is not None and sid in self._pending_entry_sids
            ):
                skipped_pending += 1
                continue

            # Hard cap: refuse to even evaluate INITIAL signals once the
            # projected open count would exceed MAX_POSITIONS_OPEN. ADD
            # signals don't grow the trade count, so always allowed here.
            is_existing_trade = (
                key in active_keys
                or self._positions.has_position_for_sid(sid)
            )
            if not is_existing_trade and projected_open >= config.MAX_POSITIONS_OPEN:
                skipped_full += 1
                continue

            signal = self._entries.evaluate(
                key, indicators, projected_open_count=projected_open
            )
            if signal is None:
                continue

            # Weekly INITIAL-entry throttle. ADDs are exempt (already capped
            # by PYRAMID_MAX_ADDS and require an existing position).
            if signal == EntrySignal.INITIAL and (
                len(self._initial_entry_history)
                >= config.MAX_NEW_INITIAL_ENTRIES_PER_WEEK
            ):
                skipped_throttle += 1
                continue

            signals_fired += 1

            # Lazy-load the option chain on the first signal for this underlying.
            self._ensure_option_subscription(symbol, key)
            self._pending_entries.append(
                {
                    "underlying": symbol,
                    "underlying_key": key,
                    "sid": sid,
                    "signal": signal,
                    "queued_date": self.time.date(),
                    "underlying_price": float(sec.price),
                }
            )
            self._pending_entry_underlyings.add(key)
            if sid is not None:
                self._pending_entry_sids.add(sid)
            self._pending_entry_first_seen.setdefault(key, self.time.date())

            if signal == EntrySignal.INITIAL:
                self._initial_entry_history.append(today)
                projected_open += 1
                if projected_open >= config.MAX_POSITIONS_OPEN:
                    skipped_full += 1
                    break

        if signals_fired or self._pending_entries or self._pending_orders:
            self.debug(
                f"[EVAL] {self.time.date()} signals={signals_fired} "
                f"skip_pending={skipped_pending} skip_full={skipped_full} "
                f"skip_throttle={skipped_throttle} "
                f"throttle_history={len(self._initial_entry_history)}/{config.MAX_NEW_INITIAL_ENTRIES_PER_WEEK} "
                f"pending_entries={len(self._pending_entries)} "
                f"pending_orders={len(self._pending_orders)} "
                f"pending_underlyings={len(self._pending_entry_underlyings)} "
                f"reserved_cash={self._reserved_cash:.0f} "
                f"cash={float(self.portfolio.cash):.0f} "
                f"open_trades={len(self._positions.active_trades)} "
                f"subs={len(self._subscribed_options)}"
            )

        # Daily book-health diagnostic. `orphans` should always be 0 — any
        # nonzero value flags a bug in close-leg promotion / reconciliation.
        orphans = sum(
            1 for t in self._positions.active_trades.values() if not t.open_legs
        )
        active_keys = set(self._positions.active_trades.keys())
        stale_pending_keys = sum(
            1
            for k in self._pending_entry_underlyings
            if k not in active_keys
            and not any(m.get("underlying") == k for m in self._pending_orders.values())
        )
        current_trade_count = len(self._positions.active_trades)
        delta = current_trade_count - self._prev_trade_count
        delta_str = f"+{delta}" if delta >= 0 else f"{delta}"
        self.debug(
            f"[BOOK-HEALTH] {self.time.date()} "
            f"trades={current_trade_count} "
            f"delta={delta_str} "
            f"orphans={orphans} "
            f"pending_underlyings={len(self._pending_entry_underlyings)} "
            f"stale_pending={stale_pending_keys} "
            f"subs={len(self._subscribed_options)} "
            f"sid_idx={len(getattr(self._positions, '_trades_by_sid', {}))}"
        )
        self._prev_trade_count = current_trade_count

        # Phantom-state detector: dump book contents whenever it grows past the
        # configured cap or pending orders accumulate. Fires on any day, not
        # just Monday — we need maximum signal once the leak appears.
        if (
            len(self._positions.active_trades) > config.MAX_POSITIONS_OPEN
            or len(self._pending_orders) > 5
        ):
            trade_keys = list(self._positions.active_trades.keys())[:25]
            order_keys = list(self._pending_orders.keys())[:25]
            order_types = [
                f"{oid}:{m.get('type', '?')}:{m.get('underlying', '?')}"
                for oid, m in list(self._pending_orders.items())[:10]
            ]
            self.debug(
                f"[BOOK-DUMP] {self.time.date()} "
                f"trades({len(self._positions.active_trades)})={trade_keys} "
                f"orders({len(self._pending_orders)})={order_keys} "
                f"first10={order_types}"
            )

    # ------------------------------------------------------------------
    # Option subscription / chain handling
    # ------------------------------------------------------------------
    def _ensure_option_subscription(self, underlying_symbol, key: str) -> None:
        sid = self._sid_key(underlying_symbol)
        # SID-keyed cache: a mapfile rename of the same underlying re-uses the
        # existing canonical option Symbol and avoids a duplicate subscription.
        cache_key = sid if sid is not None else key
        if cache_key in self._subscribed_options:
            return
        try:
            option = self.add_option(underlying_symbol, Resolution.DAILY)
        except Exception as exc:  # noqa: BLE001
            self.debug(f"[OPTION-SUB FAIL] {key}: {exc}")
            return
        try:
            option.set_filter(
                lambda u: u.calls_only()
                .expiration(config.OPTION_DTE_MIN, config.OPTION_DTE_MAX)
                .delta(config.OPTION_DELTA_MIN, config.OPTION_DELTA_MAX)
            )
        except Exception:  # noqa: BLE001
            try:
                option.set_filter(
                    lambda u: u.expiration(config.OPTION_DTE_MIN, config.OPTION_DTE_MAX)
                )
            except Exception:  # noqa: BLE001
                pass
        self._subscribed_options[cache_key] = option.symbol
        self.debug(f"[OPTION-SUB] {key} sid={sid} canonical={option.symbol}")

    def _process_pending_entries(self, slice) -> None:
        if not self._pending_entries:
            return
        still_pending = []
        cutoff = 5  # days before we drop a stale signal
        for entry in self._pending_entries:
            key = entry["underlying_key"]
            sid = entry.get("sid")
            age_days = (self.time.date() - entry["queued_date"]).days
            cache_key = sid if sid is not None else key
            opt_symbol = self._subscribed_options.get(cache_key)
            if opt_symbol is None:
                # Subscription not yet active; keep until cutoff, then drop.
                if age_days <= cutoff:
                    still_pending.append(entry)
                else:
                    self.debug(f"[ENTRY-DROP no-sub] {key} age={age_days}")
                    self._discard_pending_entry(key, sid)
                continue

            chain = None
            try:
                chains = getattr(slice, "option_chains", None) or getattr(
                    slice, "OptionChains", None
                )
                if chains is not None:
                    chain = chains.get(opt_symbol)
            except Exception:  # noqa: BLE001
                chain = None

            if not chain:
                if age_days <= cutoff:
                    if age_days >= 1:
                        self.debug(
                            f"[ENTRY-WAIT no-chain] {key} age={age_days} "
                            f"opt={opt_symbol}"
                        )
                    still_pending.append(entry)
                else:
                    self.debug(f"[ENTRY-DROP no-chain] {key} age={age_days}")
                    self._discard_pending_entry(key, sid)
                continue

            try:
                chain_size = sum(1 for _ in chain)
            except Exception:  # noqa: BLE001
                chain_size = -1

            record = self._selector.select(key, chain, today=self.time.date())
            if record is None:
                # Chain populated but nothing qualifies — drop the signal.
                self.debug(
                    f"[ENTRY-DROP selector-reject] {key} chain_size={chain_size}"
                )
                self._discard_pending_entry(key, sid)
                continue

            # Reserve cash for orders already submitted but not yet filled
            # (DAILY-resolution MOO orders fill on the next session).
            available_cash = max(0.0, float(self.portfolio.cash) - self._reserved_cash)
            contracts = self._pyramiding.size_leg(record.mid_price, available_cash)
            if contracts <= 0:
                self.debug(
                    f"[ENTRY-DROP no-cash] {key} mid={record.mid_price:.2f} "
                    f"avail={available_cash:.0f} reserved={self._reserved_cash:.0f}"
                )
                self._discard_pending_entry(key, sid)
                continue

            self._submit_entry(entry, record, contracts)

        self._pending_entries = still_pending

    # ------------------------------------------------------------------
    # Pending-entry housekeeping
    # ------------------------------------------------------------------
    def _discard_pending_entry(self, key: str, sid) -> None:
        """Release both the bare-ticker and SID guard slots for a dropped entry."""
        self._pending_entry_underlyings.discard(key)
        self._pending_entry_first_seen.pop(key, None)
        if sid is not None:
            self._pending_entry_sids.discard(sid)

    def _sweep_stale_pending_entries(self) -> None:
        """Discard any _pending_entry_underlyings key that has lingered without
        a matching _pending_entries item OR _pending_orders meta for longer
        than 7 calendar days. This catches leaked guard keys whose entry was
        dropped through a code path that forgot to call _discard_pending_entry."""
        ttl_days = 7
        today = self.time.date()
        live_pending_keys = {e["underlying_key"] for e in self._pending_entries}
        live_pending_sids = {e.get("sid") for e in self._pending_entries if e.get("sid")}
        live_order_keys = {
            m.get("underlying")
            for m in self._pending_orders.values()
            if m.get("type") in (EntrySignal.INITIAL, EntrySignal.ADD)
        }
        for key in list(self._pending_entry_underlyings):
            if key in live_pending_keys or key in live_order_keys:
                continue
            first_seen = self._pending_entry_first_seen.get(key, today)
            age = (today - first_seen).days
            if age >= ttl_days:
                self.debug(
                    f"[PENDING-SWEEP] dropping stale key={key} age={age}d"
                )
                self._pending_entry_underlyings.discard(key)
                self._pending_entry_first_seen.pop(key, None)
        # Drop pending SIDs that no longer correspond to any live entry/order.
        for sid in list(self._pending_entry_sids):
            if sid in live_pending_sids:
                continue
            self._pending_entry_sids.discard(sid)

    def _option_mid(self, contract_symbol) -> float:
        """Return current mid premium for an option contract from securities cache."""
        if contract_symbol is None:
            return 0.0
        sec = None
        try:
            sec = self.securities.get(contract_symbol)
        except Exception:  # noqa: BLE001
            sec = None
        if sec is None:
            for k in self.securities.keys:
                if str(k) == str(contract_symbol):
                    sec = self.securities[k]
                    break
        if sec is None:
            return 0.0
        bid = float(getattr(sec, "bid_price", 0.0) or 0.0)
        ask = float(getattr(sec, "ask_price", 0.0) or 0.0)
        if bid > 0 and ask > 0:
            return (bid + ask) / 2.0
        return float(getattr(sec, "price", 0.0) or 0.0)

    # ------------------------------------------------------------------
    # Exit application
    # ------------------------------------------------------------------
    def _apply_exit_decisions(self, underlying_str: str, trade, decisions) -> None:
        if not decisions:
            return
        # Trade-wide rule: leg=None means liquidate every open leg.
        for leg, reason in decisions:
            if leg is None:
                for open_leg in list(trade.open_legs):
                    self._submit_leg_exit(underlying_str, open_leg, reason, trade_wide=True)
                return
        # Per-leg rules
        for leg, reason in decisions:
            self._submit_leg_exit(underlying_str, leg, reason, trade_wide=False)

    # ------------------------------------------------------------------
    def _submit_entry(self, entry: dict, record, contracts: int) -> None:
        key = entry["underlying_key"]
        sid = entry.get("sid")
        reserved_cost = (
            float(record.mid_price) * float(contracts) * float(config.OPTION_CONTRACT_MULTIPLIER)
        )
        meta = {
            "underlying": key,
            "sid": sid,
            "live_symbol": entry["underlying"],
            "type": entry["signal"],
            "contract_symbol": record.contract_symbol,
            "expiry": record.expiry,
            "strike": record.strike,
            "delta": record.delta,
            "underlying_price": entry.get("underlying_price", 0.0),
            "reserved_cost": reserved_cost,
        }
        # Reserve cash BEFORE submitting; if market_order fills synchronously
        # we will release it inline below.
        self._reserved_cash += reserved_cost
        ticket = self.market_order(record.contract_symbol, contracts)
        if ticket is None:
            self.debug(f"[ENTRY-DROP no-ticket] {key} contract={record.contract_symbol}")
            self._discard_pending_entry(key, sid)
            self._reserved_cash = max(0.0, self._reserved_cash - reserved_cost)
            return
        self.debug(
            f"[ENTRY-SUBMIT] {key} oid={ticket.order_id} "
            f"contract={record.contract_symbol} contracts={contracts} "
            f"mid={record.mid_price:.2f} reserved+={reserved_cost:.0f} "
            f"ticket_status={ticket.status}"
        )
        # If LEAN filled synchronously (events fired inside market_order before
        # we could register meta), apply the fill here from ticket state.
        if self._is_terminal_status(ticket.status):
            self._apply_terminal_inline(ticket, meta)
            return
        self._pending_orders[ticket.order_id] = meta

    def _submit_leg_exit(self, underlying_str: str, leg, reason: str, trade_wide: bool) -> None:
        if leg.contract_symbol is None or leg.quantity <= 0:
            return
        # Skip if a close order is already in flight for this leg — DAILY-resolution
        # market orders convert to MOO and fill on the next session, so we must not
        # re-submit until the prior order resolves (otherwise duplicate fills create
        # short positions and exhaust margin).
        if getattr(leg, "pending_exit", False):
            return
        meta = {
            "underlying": underlying_str,
            "type": "EXIT_TRADE" if trade_wide else "EXIT_LEG",
            "leg": leg,
            "reason": reason,
            "contract_symbol": leg.contract_symbol,
        }
        leg.pending_exit = True
        # Stash intended reason BEFORE submitting so the on_order_event
        # reconcile path (which fires synchronously inside market_order on
        # DAILY resolution) records the correct exit reason instead of MANUAL.
        leg.exit_reason = reason
        ticket = self.market_order(leg.contract_symbol, -leg.quantity)
        if ticket is None:
            leg.pending_exit = False
            return
        self.debug(
            f"[EXIT-SUBMIT] {underlying_str} oid={ticket.order_id} "
            f"contract={leg.contract_symbol} qty={-leg.quantity} reason={reason} "
            f"ticket_status={ticket.status}"
        )
        # Synchronous fill path: events already fired with no-meta; apply inline.
        if self._is_terminal_status(ticket.status):
            self._apply_terminal_inline(ticket, meta)
            return
        self._pending_orders[ticket.order_id] = meta

    # ------------------------------------------------------------------
    # Synchronous-fill helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _is_terminal_status(status) -> bool:
        return status in (
            OrderStatus.FILLED,
            OrderStatus.INVALID,
            OrderStatus.CANCELED,
        )

    def _apply_terminal_inline(self, ticket, meta: dict) -> None:
        """Process a market_order that already reached a terminal status before
        we could register meta in _pending_orders. Mirrors on_order_event but
        sources fill price/qty from the ticket itself."""
        status = ticket.status
        underlying = meta["underlying"]

        if status != OrderStatus.FILLED:
            if meta["type"] in (EntrySignal.INITIAL, EntrySignal.ADD):
                self._discard_pending_entry(underlying, meta.get("sid"))
                self._reserved_cash = max(
                    0.0, self._reserved_cash - float(meta.get("reserved_cost", 0.0))
                )
            elif meta["type"] in ("EXIT_LEG", "EXIT_TRADE"):
                leg = meta.get("leg")
                if leg is not None:
                    leg.pending_exit = False
            self.debug(
                f"[INLINE-NOFILL] oid={ticket.order_id} status={status} "
                f"underlying={underlying} type={meta['type']}"
            )
            return

        try:
            fill_price = float(ticket.average_fill_price)
        except Exception:  # noqa: BLE001
            fill_price = 0.0
        try:
            fill_qty = abs(int(ticket.quantity_filled))
        except Exception:  # noqa: BLE001
            fill_qty = abs(int(getattr(ticket, "quantity", 0)))

        if meta["type"] in (EntrySignal.INITIAL, EntrySignal.ADD):
            self._discard_pending_entry(underlying, meta.get("sid"))
            self._reserved_cash = max(
                0.0, self._reserved_cash - float(meta.get("reserved_cost", 0.0))
            )
            self._positions.add_leg(
                symbol=underlying,
                fill_price=fill_price,
                quantity=fill_qty,
                fill_date=self.time.date(),
                contract_symbol=meta.get("contract_symbol"),
                expiry=meta.get("expiry"),
                strike=meta.get("strike", 0.0),
                delta_at_entry=meta.get("delta", 0.0),
                underlying_price_at_entry=meta.get("underlying_price", 0.0),
                live_symbol=meta.get("live_symbol"),
            )
            self.log(
                f"[FILL ENTRY/{meta['type']}] (inline) {underlying} "
                f"contract={meta.get('contract_symbol')} contracts={fill_qty} "
                f"@ premium {fill_price:.2f}"
            )
            return

        if meta["type"] in ("EXIT_LEG", "EXIT_TRADE"):
            leg = meta.get("leg")
            if leg is not None:
                leg.pending_exit = False
            trade = self._positions.get_trade(underlying)
            if trade is not None and leg is not None:
                result = self._positions.close_leg(
                    underlying,
                    leg,
                    fill_price,
                    meta.get("reason", config.EXIT_REASON_MANUAL),
                )
                tag = "EXIT-LEG" if meta["type"] == "EXIT_LEG" else "EXIT-TRADE"
                if result:
                    self.log(
                        f"[FILL {tag}] (inline) {underlying} contracts={fill_qty} "
                        f"@ {fill_price:.2f} P&L={result['pnl']:.2f} "
                        f"reason={result['reason']}"
                    )
                else:
                    self.debug(
                        f"[INLINE-EXIT-MISS] {underlying} leg.status={leg.status} "
                        f"in_legs={leg in trade.legs}"
                    )
