# Silent Failure Modes

**Source:** `handlers/`, `config.py`, QC Documentation (crawl_date: 2026-03-23)
**Category:** debugging
**Status:** ✅ Populated — known silent failure patterns for this codebase

---

## Overview

Silent failures are conditions where the algorithm runs without errors but produces
incorrect or missing behavior. These are harder to detect than exceptions.

---

## Cache-Related Failures

- **Stale cache not cleared** — `data_handler.clear_cache()` not called before scan →
  yesterday's indicators used for today's signals. Always call at top of `_scan_universe()`.
- **Wrong symbol type in cache key** — passing a `Symbol` object instead of `str(symbol)` →
  cache miss every call, redundant `history()` API calls, slower scan.

```python
# Correct:
cache_key = (str(symbol), today)   # DataHandler uses this internally
```

---

## Empty Dict Propagation

- `DataHandler.get_indicators()` returns `{}` on insufficient history
- If the caller does not guard `if not indicators: continue`, downstream code raises
  `KeyError` on `indicators["price"]` etc. — or worse, silently proceeds with default `0`
- Most common at algorithm start before warm-up completes (first 70 bars)

```python
# Always guard:
indicators = self._data_handler.get_indicators(symbol)
if not indicators:
    continue
```

---

## Options Chain Failures

- `option_chains` returns `[]` for a symbol if `add_option(equity_symbol)` was never
  called → `has_weekly_options()` returns `False`, all setups blocked. For universe-based
  strategies, `add_option()` must be called per-equity inside `on_securities_changed()`,
  and `option.symbol` (the canonical key) must be stored separately.
  not in `initialize()`.
- `option_chains` is keyed by the **canonical option symbol** returned as `option.symbol` from
  `add_option()`,
  **not** by the equity symbol string. Always store the mapping:
  `self._option_symbols[str(equity_symbol)] = option_chain_symbol`
  and resolve it before calling `option_chains.get(...)`.
- Open interest is `0` during warm-up (no real trading occurs) → OI gate
  (`OpenInterest >= 1000`) rejects all contracts → `instrument_selector` returns `None`
- `getattr(contract, "OpenInterest", getattr(contract, "open_interest", 0))` — both
  attribute case formats are tried; if neither exists, `0` is returned silently

---

## Earnings Date Failures

- **`security.fundamentals` unreliable in scheduled events** — Inside a `schedule.on()`
  callback, `security.fundamentals` is not guaranteed to be populated for symbols added via
  `ManualUniverseSelectionModel`. It may return `None` or a stale fill-forwarded object.
  Always use `self.history[Fundamental](symbol, timedelta(days=N))` inside scheduled events
  to get reliable point-in-time Morningstar data.

```python
# CORRECT — always works in scheduled events
fund_history = list(self.history[Fundamental](security.symbol, timedelta(days=120)))
if not fund_history:
    continue  # no Morningstar coverage for this ticker
raw = fund_history[-1].financial_statements.period_ending_date.value
```

- **`earnings_history` never populated → Gate 3 always fails** — `setup_checker.py` reads
  `getattr(algorithm, "earnings_history", {}).get(symbol, [])`. If `earnings_history` is
  missing or empty, `_assess_optimism_track_record([])` returns `0.0`, which is always
  `< _OPTIMISM_PASS_RATE (0.75)` — every symbol is silently blocked. Confirm
  `self.earnings_history = {}` is in `initialize()` and `_populate_earnings_history()` is
  called in `_scan_universe()`.
- Earnings date stored as `datetime` vs `date` — `(earnings_date - today).days` raises
  `TypeError`. `EarningsCalendar._refresh_cache()` normalises with
  `isinstance(raw_date, datetime)` → `raw_date.date()` — this is handled, but custom
  injected test data must also pass `date` objects or `datetime` objects (not strings).
- Earnings date not in calendar → `days_until_earnings()` returns `None` →
  `is_within_entry_window()` returns `False` — gate correctly blocks, but no log
  message is emitted. Add a `self.log()` call after any `None` check if diagnostics needed.
- `invalidate_cache()` not called between daily scans → stale `(earnings_date, type)`
  cached from prior day → incorrect `days_to_earnings` values (off by 1 each day).

---

## Scheduling Failures

- **Market holidays** — QC's `schedule.on(date_rules.every_day(...), ...)` events do
  **not** fire on market holidays. This is expected and correct — no special handling needed.
- **Time rule fires outside market hours** — if `time_rules.at(hour, minute)` is used
  with a time before open or after close, the event fires at the next valid market time.
  Use `before_market_close()` / `after_market_open()` for reliable timing.
- **Scheduled function throws exception** — LEAN catches exceptions inside scheduled
  functions and logs them, but does **not** halt the algorithm. The scan silently skips
  that day. Always wrap scheduled callbacks in try/except with explicit logging.
- **Wrong reference security for time rule** — `time_rules.before_market_close("SPY", 30)`
  uses SPY's market hours. If a different security is passed that has extended hours,
  the event will fire at a different time than expected.

---

## Fill Reconciliation Failures

- **Order ID mismatch** — `on_order_event()` fires for **all** orders (entry and exit).
  If `pending_orders` dict is not keyed by `order_event.order_id`, fills may be matched
  to the wrong position or ignored.
- **Partial fills** — a single `market_order()` can trigger multiple `on_order_event()`
  callbacks with `OrderStatus.PARTIALLY_FILLED` before the final `FILLED`. If the code
  only handles `FILLED`, intermediate fills are missed and position state is never updated
  until the final fill — which may be much later.

```python
def on_order_event(self, order_event: OrderEvent) -> None:
    if order_event.status not in (OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED):
        return
    # Accumulate fill_quantity, don't assume one fill = full order
```

- **Option contract fill price in bid/ask units** — option `fill_price` in QC is per-share
  (1 contract = 100 shares). `total_cost = fill_price * 100 * quantity`. Forgetting the
  multiplier causes 100× underreporting of cost basis.

---

## IV Data Not Populated

- `algorithm.iv_data` is an injectable test slot, not a native QC feed
- In production it must be populated from the options chain before `SetupChecker` runs
- If `iv_data = {}`, `get_implied_volatility()` returns `0.0` →
  `compare_iv_vs_rolling_average()` → `1.0` (not elevated) →
  `is_iv_already_elevated()` returns `False` — **silent false-pass of the IV gate**
- Fix: Populate `iv_data` from `OptionUniverse.implied_volatility` during the scan:

```python
for option_universe in self.option_chain(symbol):
    self.iv_data[str(symbol)] = float(option_universe.implied_volatility) * 100.0
```

---

## History Returns Wrong Column Names

- `DataHandler._extract_column(history, "close")` tries both `"close"` and `"Close"`
- If a custom history object has different column names (e.g., from a third-party dataset),
  `closes` will be empty → `get_indicators()` returns `{}` → silent skip
- Always verify history DataFrame has standard OHLCV columns before passing to `DataHandler`

---

## Synchronous on_order_event — _pending_orders Race Condition

In LEAN's **daily-resolution backtest**, `market_order()` fills at the current bar price
synchronously. `on_order_event()` fires **inside** `market_order()` before the call
returns, so any dict populated after the call is always too late:

```python
# BUG — on_order_event fires during market_order(), before line B executes
ticket = self.market_order(symbol, qty)              # line A — event fires here
self._pending_orders[ticket.order_id] = meta         # line B — unreachable in time
```

**Symptom:** `[HOLDINGS] positions=0/10 cash=-0 portfolio=$108k` for every bar.
LEAN holds the equity; `active_trades` stays permanently empty because `add_leg()` is
never called. `can_add_position()` always returns `True`, entries re-submit every bar
until cash hits zero, then the algorithm is frozen.

**Fix — use order tags (embedded at creation, always accessible):**

```python
# Entry submit — tag travels with the order:
self.market_order(symbol, qty, tag=f"{signal}|{sym_str}")
# e.g. tag = "INITIAL|AAPL R735QTJ8XC9X"

# Exit submit:
self.market_order(sec, -qty, tag=f"EXIT|{symbol_str}|{reason}")
self.market_order(sec, -qty, tag=f"PARTIAL_EXIT|{symbol_str}|{reason}")

# on_order_event — retrieve from ticket, no dict needed:
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
    order_type, symbol = parts[0], parts[1] if len(parts) > 1 else ""
    reason = parts[2] if len(parts) > 2 else ""
    ...
```

**Do not use** temporary placeholder string keys — `on_order_event` uses the real integer
`order_event.order_id`, which will never match a string temp key.

**Related:** stale `active_trades` during the entry loop (filled asynchronously from the
algorithm's perspective despite LEAN's synchronous firing) — use an `_initial_pending`
integer counter to track submitted-but-not-yet-reflected INITIAL orders within the bar.
