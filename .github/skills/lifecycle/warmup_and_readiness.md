# Warmup and Readiness

**Source:** `main.py`, `handlers/data_handler.py`
**Category:** lifecycle
**Invariant level:** MUST — tests enforce these rules

---

## Overview

The algorithm uses QuantConnect's built-in warm-up mechanism to pre-populate indicator
history before the backtest start date. `DataHandler` is history-injection-friendly,
meaning it will compute correct indicators from any pre-fetched history slice without
requiring platform warm-up in unit tests.

---

## Warm-Up Configuration (`main.py`)

```python
self.set_start_date(2020, 1, 1)
self.set_end_date(2024, 12, 31)
self.set_cash(100_000)
```

Warm-up is controlled via the LEAN platform. The `DataHandler` lookback is:

```python
lookback = config.SMA_50_PERIOD + 20  # 70 bars
```

This ensures SMA-50 is fully seeded at the first live bar. The algorithm should call
`self.set_warm_up(70)` (or equivalent) in `initialize()` to match this lookback.

---

## Handler Initialization Order

All handlers are instantiated in `initialize()` in this dependency order:

```
1. UniverseFilter(self)         → self._universe (no deps)
2. DataHandler(self)            → self._data_handler
3. EarningsCalendar(self)       → self._earnings_calendar
4. LevelDetector(self)          → self._level_detector
5. OptionAnalytics(self)        → self._option_analytics
6. TechnicalValidator(self)     → self._technical_validator
7. InstrumentSelector(self)     → self._instrument_selector
8. PositionManager(self)        → self._position_manager
9. SetupChecker(self, ...)      → self._setup_checker (receives all above)
```

`SetupChecker` is last because it takes references to all other handlers. Never reorder
steps 2–8; `SetupChecker` depends on all of them.

---

## Three-Phase Daily Schedule

```
Before market open (-30 min):     _scan_universe()
Before market close (-15 min):    _check_entry_triggers()
After market open (+5 min):       _check_exit_conditions()
Before market close (-5 min):     _check_exit_conditions()
```

### Scan Phase (`_scan_universe`)
1. `data_handler.clear_cache()` — resets today's indicator cache
2. Iterate universe symbols
3. `data_handler.get_indicators(symbol)` — computes + caches
4. `setup_checker.validate_setup(symbol, price)` — Phase 1 gate
5. Passing symbols stored in `self._pending_entry_signals`

### Entry Trigger Phase (`_check_entry_triggers`)
1. Iterate `_pending_entry_signals`
2. `setup_checker.check_entry_trigger(symbol, price, prior_bar)` — Phase 2 re-check
3. Check `len(self._position_manager._trades) < MAX_POSITIONS_OPEN`
4. `instrument_selector.select_instrument(symbol)` — contract selection
5. Place order via `self.market_order()`
6. Remove signal from `_pending_entry_signals`

### Exit Phase (`_check_exit_conditions`)
1. Iterate active positions in `_position_manager`
2. `position_manager.check_exit_conditions(instrument_symbol, price, delta)`
3. On `should_exit = True` → `self.liquidate(instrument_symbol)`
4. `position_manager.close_trade(instrument_symbol, exit_price, reason)`

---

## Readiness Guards

Handlers must not be called before `initialize()` completes. The scheduled functions
are all bound methods on `StrategyAlgorithm` and will not be invoked before
the platform has finished `initialize()`.

In tests, handlers are instantiated directly with mock `algorithm` objects from
`type_stubs.py` — no LEAN platform lifecycle is required.

---

## `on_order_event()` Fill Reconciliation

When an order fills:
1. Identify the fill from `self._pending_orders[event.order_id]`
2. Call `position_manager.add_trade(...)` with the actual fill price
3. Remove from `_pending_orders`

Partial fills are handled by `PositionManager.add_trade()`'s accumulation logic — if the
same instrument is filled again, it updates the weighted-average entry price.
