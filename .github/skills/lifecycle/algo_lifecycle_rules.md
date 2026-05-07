# Algo Lifecycle Rules

**Source:** QC Documentation (rag/data/doc_store.json — crawl_date: 2026-03-23),
`main.py`, `config.py`
**Category:** lifecycle
**Status:** ✅ Populated — derived from scraped QC docs + handler source

---

## Overview

LEAN calls `initialize()` **once** at algorithm start. All subscriptions, warm-up,
scheduled events, and handler construction happen here. After that, LEAN drives the
algorithm through event callbacks (`on_data`, `on_order_event`, scheduled functions).
No code outside of these callbacks is called by the platform.

---

## initialize()

Called once at algorithm start. Must contain:
- `set_start_date()` / `set_end_date()` — backtest date range (ignored in live)
- `set_cash()` — starting portfolio value
- `add_equity()` — equity subscriptions (option chains are wired in `on_securities_changed()`)
- `set_warm_up()` — pre-start data replay period
- `schedule.on()` — timed event registration
- Handler instantiation (see [warmup_and_readiness.md](warmup_and_readiness.md))

```python
def initialize(self) -> None:
    self.set_start_date(2020, 1, 1)
    self.set_end_date(2024, 12, 31)
    self.set_cash(100_000)
    self._symbol = self.add_equity("SPY").symbol
    self.set_warm_up(70)                # 70 daily bars before start
    self.schedule.on(
        self.date_rules.every_day("SPY"),
        self.time_rules.before_market_close("SPY", 30),
        self._scan_universe,
    )
```

**Cannot be called outside initialize():** `add_equity`, `set_warm_up`, `schedule.on`.

**`add_option()` must be called in `on_securities_changed()`**, not in `initialize()`.
Calling it in `initialize()` before universe equities are added produces no subscription.

### Universe Type and Fundamental Data Access

This algorithm uses `ManualUniverseSelectionModel` with a static 107-ticker list.
Fundamental data (Morningstar) is **accessible** for all subscribed equities, but the
access method matters depending on where in the lifecycle you call it:

| Context | Reliable method | Unreliable method |
|---|---|---|
| `on_data()` | `security.fundamentals` (delivered in slice) | — |
| `schedule.on()` callback | `self.history[Fundamental](symbol, timedelta(N))` | `security.fundamentals` (may be `None`) |
| `initialize()` | Neither — fundamentals not loaded yet | — |

**`ManualUniverseSelectionModel` vs Fundamental universe selector:**
- `ManualUniverseSelectionModel` — static list; fundamentals accessible via `history[Fundamental]`
  in scheduled events; universe never changes.
- Fundamental universe selector — fundamentals guaranteed delivered when symbol enters
  universe; supports dynamic filtering on fundamental criteria; universe can shrink/grow.

For this strategy, `ManualUniverseSelectionModel` is intentional — the 107 tickers are
pre-researched earnings candidates. Use `history[Fundamental]` in all scheduled event
callbacks that need Morningstar data.

---

## on_securities_changed()

Fires when the universe composition changes — equities are added or removed. This is the
correct place to subscribe option chains for universe-based strategies.

```python
def on_securities_changed(self, changes):
    universe = set(self._universe_filter.get_universe())
    for security in changes.added_securities:
        if security.type != SecurityType.Equity:
            continue
        sym_str = str(security.symbol)
        if sym_str not in universe:
            continue  # skip SPY and other non-universe equities
        if sym_str in self._option_symbols:
            continue  # idempotent — already subscribed
        option = self.add_option(security.symbol)
        option.set_filter(
            lambda u: u.expiration(
                MIN_CALENDAR_DAYS_TO_EARNINGS,
                MAX_CALENDAR_DAYS_TO_EARNINGS + 15,
            )
        )
        self._option_symbols[sym_str] = option.symbol
```

**Key rules:**
- **Never guard `on_securities_changed` with `is_warming_up`** when using
  `ManualUniverseSelectionModel` for pre defined securities. All 107 universe securities are added during warmup,
  so `on_securities_changed` fires only during warmup for this strategy. A warmup guard
  would skip `add_option()` for every security and, because the universe is static
  (never changes post-warmup), `on_securities_changed` never fires again after warmup
  ends — leaving `_option_symbols` empty permanently. This differs from a dynamic
  universe where new equities would be added after warmup and re-trigger the callback.
  The `is_warming_up` guard is appropriate for _trading and signal logic_ inside
  `on_securities_changed`, but not for infrastructure subscriptions like `add_option()`.
- `add_option(equity_symbol)` returns an **`Option` security object**; its `.symbol` attribute
  is the **canonical option symbol** — a different key from the equity symbol string
- `self.option_chains` in `on_data` / handlers is keyed by this canonical option symbol,
  not by `str(equity_symbol)`
- Always maintain a mapping `self._option_symbols = {equity_str: option_symbol}` and pass
  it to `InstrumentSelector` via `getattr(algorithm, "_option_symbols", {})`
- The `+15` day buffer on `MAX_CALENDAR_DAYS_TO_EARNINGS` ensures a Friday expiry always
  exists at the far edge of the 30-day entry window

---

## on_data()

Fires at each data event. For **daily resolution**, fires at market close (16:00 ET).
Receives a `Slice` object — a dictionary-like container holding all subscribed data
for the current time step.

```python
def on_data(self, slice: Slice) -> None:
    if self.is_warming_up:
        return          # Do not trade during warm-up

    # Access equity bar
    bar = slice.bars.get(self._symbol)
    if bar is None:
        return          # No data this bar (holiday, halted)

    # Access option chain
    chain = slice.option_chains.get(self._option_symbol)
```

**Key rules:**
- Always guard `self.is_warming_up` at the top. QC fires `on_data` during warm-up.
- Daily bars are delivered at market close — `self.time` equals 16:00 ET on the bar date.
- Option chain data is available inside `slice.option_chains[option_symbol]`.
- `slice.bars.TryGetValue` pattern (C#) maps to `slice.bars.get(symbol)` in Python.

---

## on_order_event()

Fires when an order changes state. Used for fill reconciliation only — do not place
new orders here (risk of re-entry loops).

```python
def on_order_event(self, order_event: OrderEvent) -> None:
    if order_event.status == OrderStatus.FILLED:
        fill_price = order_event.fill_price
        fill_qty   = order_event.fill_quantity
        order_id   = order_event.order_id
        # Match against pending_orders dict by order_id
```

**OrderEvent fields:**
| Field | Type | Notes |
|---|---|---|
| `order_id` | int | Matches the return value of `market_order()` etc. |
| `status` | `OrderStatus` | `FILLED`, `PARTIALLY_FILLED`, `CANCELED`, `INVALID` |
| `fill_price` | float | Actual fill price (0.0 if not filled) |
| `fill_quantity` | float | Quantity filled this event (partial fills fire multiple events) |
| `symbol` | Symbol | Contract symbol that was traded |

**Partial fills:** A single order can fire multiple `on_order_event` callbacks. Accumulate
`fill_quantity` until `status == FILLED` or `CANCELED`.

---

## Scheduled Events

Created in `initialize()` using `schedule.on(date_rule, time_rule, function)`.
This strategy's schedule (from `config.py`):

```python
# Scan universe: 30 min before market open
self.schedule.on(
    self.date_rules.every_day("SPY"),
    self.time_rules.before_market_close("SPY", 30),
    self._scan_universe,
)

# Entry trigger check: 15 min before close
self.schedule.on(
    self.date_rules.every_day("SPY"),
    self.time_rules.before_market_close("SPY", 15),
    self._check_entry_triggers,
)

# Exit checks: multiple times (from EXIT_CHECK_TIMES in config.py)
self.schedule.on(
    self.date_rules.every_day("SPY"),
    self.time_rules.after_market_open("SPY", 5),
    self._check_exit_conditions,
)
```

**`date_rules` options:** `every_day(symbol)`, `week_start(symbol)`, `week_end(symbol)`,
`month_start(symbol)`, `month_end(symbol)`.

**`time_rules` options:** `before_market_close(symbol, minutes)`,
`after_market_open(symbol, minutes)`, `at(hour, minute)`, `every(timedelta)`.

**Market holidays:** Scheduled events do **not** fire on market holidays. No special
handling required — the event silently skips.

---

## Warm-Up Phase

Warm-up replays historical data from before `set_start_date()` to seed indicators.
Trades **cannot** be placed during warm-up.

```python
self.set_warm_up(70)                        # 70 daily bars
# or
self.set_warm_up(70, Resolution.DAILY)      # explicit resolution
```

Guard in all callbacks:

```python
if self.is_warming_up:
    return
```

This strategy needs `SMA_50_PERIOD + 20 = 70` bars minimum. See
[warmup_and_readiness.md](warmup_and_readiness.md) for full warm-up rules.

---

## Algorithm End

`on_end_of_algorithm()` fires once after the last data bar. Use for final cleanup,
summary logging, or position assertions. Do not place orders here — they will not
fill after backtest end.

```python
def on_end_of_algorithm(self) -> None:
    self.log(f"Closed trades: {len(self._position_manager.closed_trades)}")
```
