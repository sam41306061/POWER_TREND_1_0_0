# Why Didn't My Algorithm Trade?

**Source:** `handlers/`, `config.py`, QC Documentation (crawl_date: 2026-03-23)
**Category:** debugging
**Status:** ✅ Populated — diagnostic checklist for missed entries

---

## Overview

Use this checklist when the algorithm runs without errors but places no orders.
Work through the phases in order — each phase gate must pass before the next is evaluated.

---

## Phase 1 (Scan) Silent Failures

Run at `SCAN_SCHEDULE_TIME` (`09:35` by default, from `config.py`). All must be `True`:

- [ ] **`earnings_within_window = False`** — earnings dates not loaded, or no symbol has
  earnings in 7–30 days. Check `algorithm.earnings_data` dict is populated and dates
  are `date` objects (not strings or `datetime`).
- [ ] **`market_regime_ok = False`** — SPY EMA(8) is below EMA(21). Check that SPY is
  subscribed in `main.py` (`add_equity("SPY")`) and history returns sufficient bars.
- [ ] **`optimism_qualified = False`** — `_assess_optimism_track_record()` returned < 0.75
  (`_OPTIMISM_PASS_RATE`). Check `algorithm.earnings_history[symbol]` is a non-empty list
  of bools (one `True`/`False` per past quarter). If the list is empty or the key is missing,
  `_assess_optimism_track_record([])` returns `0.0` and every setup is blocked silently.
  `earnings_history` is populated once on the first post-warmup scan by
  `_populate_earnings_history()` — confirm `[HISTORY] Populated N/107` appears in the
  LEAN debug log.
- [ ] **`weekly_options_available = False`** — `option_chains` returned `[]` for the symbol.
  In backtest, options must be subscribed via `add_option(symbol)` inside
  `on_securities_changed()` — not in `initialize()`. The chain is keyed by the canonical
  option symbol (`option.symbol`) returned by `add_option()`, stored in `self._option_symbols`. In
  tests, inject directly via `mock_algorithm.option_chains = {"AAPL": [...]}`.
- [ ] **`technicals_pass = False`** — price below `SMA_50`, or `EMA_8 < EMA_21 < EMA_34`
  (bearish stack), or price more than `MAX_ATR_EXTENSION_ABOVE_MEAN` (2.0) ATR above mean.
  Check `DataHandler.get_indicators()` returns valid values.
- [ ] **`iv_not_elevated = False`** — IV already expanded beyond 150% of 30-day rolling avg.
  Check `algorithm.iv_data[symbol]` is populated and `algorithm.iv_history[symbol]` has
  at least a few history values.
- [ ] **`get_indicators()` returns `{}`** — insufficient history. The lookback is
  `SMA_50_PERIOD + 20 = 70` bars. Confirm `set_warm_up(70)` is called in `initialize()`.
  In tests, pass a history DataFrame with ≥ 70 rows.

---

## Phase 2 (Entry Trigger) Silent Failures

Run at `ENTRY_TRIGGER_CHECK_TIME` (`10:00`). Symbol must still be valid:

- [ ] **`check_entry_trigger()` returns `False`** — price has moved out of the EMA entry
  zone between scan and trigger check. This is expected behavior — not a bug.
- [ ] **Max positions reached** — `len(position_manager._trades) >= MAX_POSITIONS_OPEN (10)`.
  Closed trades do not count; check `_trades` dict directly.
- [ ] **`instrument_selector.select_instrument()` returns `None`** — OI gate failed
  (`OpenInterest < 1000` = `MIN_OPEN_INTEREST_MULTIPLIER * FIXED_CONTRACTS`), no valid
  delta match, or all bid/ask spreads > `_MAX_BID_ASK_SPREAD` (0.50).

---

## Order Placement Failures

QC rejects orders silently (no exception) in these cases:
- **Insufficient buying power** — `market_order(symbol, qty)` is submitted but `OrderStatus`
  becomes `INVALID` in `on_order_event()`. Check `self.portfolio.cash` and
  `self.portfolio.margin_remaining`.
- **Market is closed** — orders placed outside exchange hours are held as pending or rejected
  depending on brokerage model. This strategy places orders at `10:00` — always within
  regular trading hours for US equities.
- **Symbol not subscribed** — placing an `add_option_contract()` and then immediately
  calling `market_order()` in the same time step can fail. Subscribe in `initialize()`
  or wait one time step.
- **Order quantity = 0** — `market_order(symbol, 0)` is silently rejected. Always validate
  `FIXED_CONTRACTS > 0` before placing.

**Detecting order rejections:**
```python
def on_order_event(self, order_event: OrderEvent) -> None:
    if order_event.status == OrderStatus.INVALID:
        self.log(f"Order rejected: {order_event.order_id} — {order_event.message}")
    if order_event.status == OrderStatus.CANCELED:
        self.log(f"Order canceled: {order_event.order_id}")
```

---

## Data Issues

- **Symbol not subscribed** — `history()` returns empty DataFrame for unsubscribed symbols.
  All universe symbols must be added via `add_equity(symbol, Resolution.DAILY)` in
  `initialize()` or via `on_securities_changed()`.
- **History returns empty DataFrame** — new symbol with < 70 trading days of history.
  `DataHandler.get_indicators()` returns `{}` and the symbol is silently skipped.
- **Option chain not loaded at scan time** — `option_chains` returns empty at `09:35` if
  `add_option(symbol)` was not called in `on_securities_changed()` when the equity
  entered the universe. Options chain data is daily; it is available from market open once
  properly subscribed.
- **Warm-up too short** — if `set_warm_up()` value is less than `SMA_50_PERIOD + 20 = 70`,
  indicators will not be ready on the first real bar. All setups blocked.

---

## Useful Debug Logging

Add these log statements to diagnose silently blocked setups:

```python
# In _scan_universe():
self.log(f"[SCAN] {symbol}: earnings_ok={earnings_ok}, regime_ok={regime_ok}, "
         f"technicals={technicals_pass}, iv_ok={iv_not_elevated}, indicators={bool(indicators)}")

# In _check_entry_triggers():
self.log(f"[ENTRY] {symbol}: trigger={trigger_ok}, positions={len(self._position_manager._trades)}, "
         f"instrument={instrument is not None}")

# In on_order_event():
self.log(f"[ORDER] id={order_event.order_id} status={order_event.status} "
         f"fill={order_event.fill_price} qty={order_event.fill_quantity}")
```
