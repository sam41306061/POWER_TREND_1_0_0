# Performance Assessment — `handlers/`

**Date:** 2026-05-08  
**Branch:** `main`  
**Framework:** Five Multipliers ([`.github/skills/performant_software/`](../../.github/skills/performant_software/five_multipliers.md))

---

## Implementation State

All handlers are fully implemented. The prior assessment (2026-05-07) was split into
"current code" and "forward-looking" sections because several handlers were stubs or
missing. That split is no longer necessary.

| Handler | State | Change from Prior |
|---|---|---|
| `data_handler.py` | ✅ Real implementation | Was stub |
| `entry_engine.py` | ✅ Real implementation | Unchanged |
| `exit_engine.py` | ✅ Real implementation | Was missing |
| `position_manager.py` | ✅ Real implementation | Refactored (Leg dataclass) |
| `pyramiding_manager.py` | ✅ Real implementation | Was missing |
| `regime_filter.py` | ✅ Real implementation | Was missing |
| `risk_manager.py` | ✅ Real implementation | Was missing |
| `universe_filter.py` | ✅ Real implementation | Was CSV-only stub |

Deleted (not used by Power Trend): `technical_validator.py`, `instrument_selector.py`,
`option_analytics.py`, `setup_checker.py`.

---

## Prior Assessment: Resolved Items

| ID | Issue | Resolution |
|---|---|---|
| W1 | `has_position_for_underlying()` O(n) scan | ✅ Fixed — now `symbol in self._trades` (O(1)) |
| W2 | `import config` inside method body | ✅ Pattern removed — no longer present |
| W3 | `add_trade()` applies ×100 options multiplier | ✅ Fixed — new `Leg` dataclass has no multiplier |
| F2 | EMA scalar loop | ✅ Confirmed correct by design — serial dependency chain, unchanged |

---

## Phase 0 — Hot Path & Working Set

The primary hot path is `_evaluate()` in `main.py`, scheduled daily at 09:35 ET.

**Execution flow:**

1. Clear cache; update risk equity
2. Fetch + compute QQQ indicators → update regime state machine
3. **Exit loop:** iterate ≤ 10 open positions → `DataHandler.get_indicators()` + `ExitEngine.check()`
4. **Entry loop:** iterate ≤ 200 universe symbols → `DataHandler.get_indicators()` + `EntryEngine.evaluate()`

The bottleneck is step 4. `DataHandler._compute()` is called once per symbol per day
(result cached); the per-call cost is where all scalar loop waste concentrates.

**Working set:**

```
~80 bars × 5 columns × 8 bytes ≈ 3.2 KB per symbol → L1 cache ✅
200 symbols total ≈ 640 KB → L2 / L3 ✅
```

Cache tier is **not** the bottleneck. All headroom is in the compute layer.

---

## Multiplier 1 — Waste

### C1 — `DataHandler._extract()`: ndarray obtained then immediately discarded into a Python list — 🔴 CRITICAL

**File:** [`handlers/data_handler.py`](../../handlers/data_handler.py)

**Current code (DataFrame path):**
```python
@staticmethod
def _extract(bars, column: str) -> list:
    if hasattr(bars, "columns") and column in getattr(bars, "columns", []):
        return list(bars[column].values)   # ← .values gives ndarray; list() throws it away
    ...
    return [float(getattr(b, column)) for b in bars]   # ← fallback: pure Python loop
```

**What is actually happening:**

`_extract()` is called **five times** per `_compute()` call — once for each of `open`,
`high`, `low`, `close`, `volume`. `_compute()` runs once per symbol per day. At 200
symbols that is **1,000 calls per daily scan**.

On the normal LEAN path, `bars[column].values` already returns an
`np.ndarray(dtype=float64)` — a C-contiguous block of 64-bit doubles with no Python
object overhead. The `list()` wrapper on the very next token immediately converts that
array into a Python `list`, allocating one Python `float` object per element (~80
objects per column). All downstream code in `_compute()` then operates on those Python
lists, paying full CPython interpreter overhead on every element access — ~181
instructions per operation instead of 1.

This single wrapping decision is the root cause of C2 and C3.

**Fix — remove the `list()` wrapper on the DataFrame path:**
```python
@staticmethod
def _extract(bars, column: str):
    if hasattr(bars, "columns") and column in getattr(bars, "columns", []):
        return bars[column].values            # np.ndarray — zero copies, no dispatch overhead
    if hasattr(bars, "__getitem__") and not isinstance(bars, list):
        try:
            return bars[column].values        # same for other DataFrame-like objects
        except Exception:
            pass
    return [float(getattr(b, column)) for b in bars]   # test-stub fallback only
```

**Why this helps:** Once `closes`, `highs`, `lows`, `opens`, and `volumes` are
`np.ndarray`, every downstream call in `_compute()` gains access to NumPy's C-level
operations with SIMD dispatch (see Multiplier 3). The SMA `sum()` operates on C doubles
via the buffer protocol; EMA seeding does the same; and C2/C3 fixes become trivially
expressible as single NumPy calls. **Estimated gain on extraction phase: 10–50×.**

---

### C2 — `DataHandler._compute()`: dollar-volume computed with a Python generator over Python floats — 🔴 CRITICAL

**File:** [`handlers/data_handler.py`](../../handlers/data_handler.py)

**Current code:**
```python
dv_lookback = config.DOLLAR_VOLUME_LOOKBACK   # 20
dollar_volume_20d = sum(
    float(closes[i]) * float(volumes[i]) for i in range(-dv_lookback, 0)
) / dv_lookback
```

**What is actually happening:**

`closes` and `volumes` are Python lists (because `_extract()` wraps the ndarray — see
C1). Each iteration of the generator does three things that all cost full CPython
dispatch: `closes[i]` list index (type-check + reference-count update), `float()`
object construction (heap allocation), and `__mul__` dispatch on the result. That is
**~3 × 181 instructions** per bar × 20 bars × 200 symbols = **~2.2 million CPython
dispatch operations per daily scan** just for this one calculation.

The `float()` calls are also strictly redundant: the values are already floats coming
out of the Python list.

**Fix — after C1 delivers ndarrays:**
```python
import numpy as np

dollar_volume_20d = float(np.multiply(closes[-20:], volumes[-20:]).mean())
```

**Why this helps:** `np.multiply` dispatches a single C-level call that multiplies two
20-element float64 arrays element-wise using a SIMD-vectorised kernel (AVX2 on modern
CPUs = 4 doubles per instruction). `.mean()` is then a second C-level call over the 20
results. The entire calculation replaces 20 Python loop iterations with 2 C-level
function calls. **Estimated gain: ~20–50× on this line; effectively free per-symbol.**

---

### C3 — `DataHandler._atr()`: O(14) Python loop for an embarrassingly parallel operation — 🔴 CRITICAL

**File:** [`handlers/data_handler.py`](../../handlers/data_handler.py)

**Current code:**
```python
@staticmethod
def _atr(highs, lows, closes, period: int) -> float:
    n = len(closes)
    if n < period + 1:
        return 0.0
    trs = []
    for i in range(n - period, n):
        hi, lo, prev_close = float(highs[i]), float(lows[i]), float(closes[i - 1])
        tr = max(hi - lo, abs(hi - prev_close), abs(lo - prev_close))
        trs.append(tr)
    return sum(trs) / period
```

**What is actually happening:**

The ATR True Range formula computes three values for each bar — `high - low`,
`|high - prev_close|`, and `|low - prev_close|` — then takes the max. Each of these 14
bars is **fully independent** of every other bar: bar i's True Range does not depend on
bar i−1's True Range. This is not a serial dependency chain like EMA; there is no
algorithmic reason for the loop.

Yet the current implementation pays CPython overhead on every element: 3 `float()`
allocations + 2 `abs()` calls + 1 `max()` call + 1 `list.append()` per iteration =
**~7 CPython operations per bar × 14 bars × 200 symbols = ~20,000 dispatches per daily
scan** for a 14-element computation that could execute as 3 array operations.

**Fix — after C1 delivers ndarrays:**
```python
import numpy as np

@staticmethod
def _atr(highs, lows, closes, period: int) -> float:
    n = len(closes)
    if n < period + 1:
        return 0.0
    hi = highs[-(period):]
    lo = lows[-(period):]
    pc = closes[-(period + 1):-1]          # previous closes aligned to [hi, lo]
    tr = np.maximum(hi - lo, np.maximum(np.abs(hi - pc), np.abs(lo - pc)))
    return float(tr.mean())
```

**Why this helps:** `np.maximum` and `np.abs` operate on all 14 elements simultaneously
via SIMD instructions. The Python call overhead is paid once per `_atr()` call (3 NumPy
function calls) instead of 14 × 7 times. The `list.append()` and intermediate `trs`
list allocation are eliminated entirely. **Estimated gain: ~10–30× on this method.**

---

### M1 — `UniverseFilter._force_include_regime()`: a `str + split + upper` chain executed per symbol — ⚠️ MEDIUM

**File:** [`handlers/universe_filter.py`](../../handlers/universe_filter.py)

**Current code:**
```python
def _force_include_regime(self, symbols: list, coarse_list: list) -> list:
    regime_str = config.REGIME_SYMBOL   # "QQQ"
    if any(str(s).split()[0].upper() == regime_str for s in symbols):
        return symbols
    for c in coarse_list:
        if str(c.symbol).split()[0].upper() == regime_str:
            return symbols + [c.symbol]
    return symbols
```

**What is actually happening:**

For each symbol in `symbols` (up to 200), the expression `str(s).split()[0].upper()`
does four things: `str()` constructs a new Python string object, `.split()` allocates
a temporary list (even though only index `[0]` is used), `[0]` indexes that list, and
`.upper()` constructs another new string. That is **~4 heap allocations per symbol** on
the 200-item membership check.

In the worst case (QQQ not in top-200, which can happen early in the backtest), the code
then falls through to a **secondary O(8,000) scan** of the full coarse universe, paying
the same 4-allocation chain per row. The final `symbols + [c.symbol]` concatenation
creates a **brand-new 201-element list** by copying all 200 existing entries.

This method runs every 14 days (~26 times per backtest year), so the wall-clock impact
is small — but the allocation pattern is avoidable and the fallback scan is fragile.

**Fix:**
```python
def _force_include_regime(self, symbols: list, coarse_list: list) -> list:
    regime_str = config.REGIME_SYMBOL              # "QQQ" — evaluated once
    symbol_strs = {str(s).split()[0].upper() for s in symbols}   # build set once
    if regime_str in symbol_strs:                  # O(1) set lookup
        return symbols
    for c in coarse_list:
        if str(c.symbol).split()[0].upper() == regime_str:
            return [*symbols, c.symbol]            # unpacking avoids full copy
    return symbols
```

**Why this helps:** Building the set once pays the allocation cost once instead of per
`any()` short-circuit. Set membership is O(1) vs O(n) iteration. The spread operator
`[*symbols, c.symbol]` is equivalent to `symbols + [c.symbol]` but avoids the
intermediate list allocation in the fallback branch.

---

### M2 — `UniverseFilter.active_symbols` + `_evaluate()`: the cache is copied twice before the entry loop — ⚠️ MEDIUM

**File:** [`handlers/universe_filter.py`](../../handlers/universe_filter.py) and [`main.py`](../../main.py)

**Current code:**
```python
# universe_filter.py
@property
def active_symbols(self) -> list:
    return list(self._cached_symbols)   # copy #1: 200-item list allocation

# main.py — _evaluate()
for symbol in list(self._universe.active_symbols):  # copy #2: wraps the copy again
```

**What is actually happening:**

`active_symbols` creates a defensive copy of `_cached_symbols` (200 items). The caller
in `_evaluate()` then wraps the result in `list()` again, creating a **second 200-item
list** from the first. Before the entry loop even begins, 400 Python object allocations
have been made to iterate a list that is never mutated by either caller.

**Fix:**
```python
# universe_filter.py — return the live list; document the no-mutation contract
@property
def active_symbols(self) -> list:
    return self._cached_symbols   # do not mutate the returned list

# main.py — iterate directly; the list() wrapper already does nothing useful
for symbol in self._universe.active_symbols:
```

**Why this helps:** Eliminates 400 object allocations that happen unconditionally every
day before any symbol is evaluated. The safety rationale for defensive copying does not
hold here — `_evaluate()` only reads the list in a `for` loop and immediately
`continue`s or processes entries.

---

### M3 — `main._submit_exit()`: linear search through `securities.keys` to find a known symbol — ⚠️ MEDIUM

**File:** [`main.py`](../../main.py)

**Current code:**
```python
def _submit_exit(self, symbol_str: str, qty: int, reason: str) -> None:
    sec = None
    for s in self.securities.keys:
        if str(s) == symbol_str:
            sec = s
            break
    if sec is None:
        return
    ticket = self.market_order(sec, -qty)
```

**What is actually happening:**

`_submit_exit()` receives a `symbol_str` (a plain string like `"AAPL"`) but
`market_order()` requires a LEAN `Symbol` object. To convert back, the code iterates
every key in `self.securities` — which holds all subscribed securities (~200 stocks +
QQQ) — calling `str(s)` on each until a match is found. In the worst case (symbol is
last or not found) this scans all ~201 entries.

This is called once per open position per daily exit check (≤10 times/day at most), so
the absolute cost is low. The larger problem is **correctness risk**: if `str(s)` format
ever changes between versions, the comparison silently fails and no exit order is
submitted. The symbol→Security mapping is already available in `_evaluate()` when
iterating `active_symbols`.

**Fix — build a `str → Symbol` dict once per daily scan:**
```python
# In _evaluate(), replace the entry loop header:
symbol_map: dict[str, Any] = {}
for symbol in self._universe.active_symbols:
    symbol_map[str(symbol)] = symbol
    ...  # rest of entry logic

# Store for _submit_exit():
self._symbol_map = symbol_map

# In _submit_exit():
def _submit_exit(self, symbol_str: str, qty: int, reason: str) -> None:
    sec = getattr(self, "_symbol_map", {}).get(symbol_str)
    if sec is None:
        return
    ticket = self.market_order(sec, -qty)
```

**Why this helps:** Replaces an O(n) string scan with a single O(1) dict lookup. Also
makes the Symbol→string mapping explicit and centralised, eliminating the risk of `str()`
format mismatch.

---

### L1 — `PositionManager.close_trade()`: leg sums computed up to 6 times in a single call — 🟢 LOW

**File:** [`handlers/position_manager.py`](../../handlers/position_manager.py)

**Current code:**
```python
def close_trade(self, symbol: str, exit_price: float, reason: str) -> Optional[dict]:
    ...
    pnl = (exit_price - trade.avg_entry_price) * trade.total_quantity  # access 1+2
    self._closed_trades.append(trade)
    return {
        ...
        "avg_entry_price": trade.avg_entry_price,   # access 3
        "total_quantity": trade.total_quantity,     # access 4
        ...
    }
```

**What is actually happening:**

`avg_entry_price` is a `@property` that internally calls `self.total_quantity` (also a
`@property`) to compute the weighted average, then sums `fill_price * quantity` over all
legs. `total_quantity` separately sums all `leg.quantity` values. Both are recomputed on
every access — Python properties have no caching.

In one `close_trade()` call the leg sums are executed this many times:
- Line `pnl = ...`: `trade.avg_entry_price` → triggers `total_quantity` (1 sum) + own weighted sum (1 sum) = **2 leg iterations**
- Line `pnl = ...`: `trade.total_quantity` directly = **1 more leg iteration**
- Line `"avg_entry_price"`: `trade.avg_entry_price` again = **2 more leg iterations**
- Line `"total_quantity"`: `trade.total_quantity` again = **1 more leg iteration**

**Total: 6 leg-sum iterations** where 2 would suffice. With `PYRAMID_MAX_ADDS = 3` (max
4 legs) this is at most 24 additions, so the absolute cost is unmeasurable. The issue is
about code clarity and the implicit coupling between `avg_entry_price` and
`total_quantity` being invisible at the call site.

**Fix — cache as locals at the top of the method:**
```python
def close_trade(self, symbol: str, exit_price: float, reason: str) -> Optional[dict]:
    trade = self._trades.pop(symbol, None)
    if trade is None:
        return None
    total_qty = trade.total_quantity      # computed once
    avg_price = trade.avg_entry_price     # computed once (calls total_qty internally)
    trade.exit_price = exit_price
    trade.exit_date = self._algo.time.date()
    trade.exit_reason = reason
    trade.status = "CLOSED"
    pnl = (exit_price - avg_price) * total_qty
    self._closed_trades.append(trade)
    return {
        "symbol": symbol, "pnl": pnl, "reason": reason,
        "avg_entry_price": avg_price, "exit_price": exit_price,
        "total_quantity": total_qty, "leg_count": trade.leg_count,
        "holding_days": (trade.exit_date - trade.entry_date).days if trade.entry_date else 0,
    }
```

---

### ✅ No Action — `DataHandler._ema()`: scalar loop is correct by design

**Current code:**
```python
@staticmethod
def _ema(values, period: int) -> float:
    if len(values) < period:
        return float("nan")
    seed = sum(values[:period]) / period
    alpha = 2.0 / (period + 1)
    ema = seed
    for v in values[period:]:
        ema = alpha * float(v) + (1 - alpha) * ema   # each output feeds the next input
    return float(ema)
```

EMA is a first-order IIR (Infinite Impulse Response) filter. The recurrence relation
`EMA_t = α × price_t + (1 − α) × EMA_{t−1}` means each output value is the **input**
to the next iteration. This is a true serial dependency chain — bar 22 cannot be
computed until bar 21 is complete, bar 23 cannot be computed until bar 22 is complete,
and so on. NumPy has no built-in function for this recurrence and expressing it with
`np.frompyfunc` or `scipy.signal.lfilter` would change the algorithm's numerical
behaviour. The scalar loop is the correct and intentional implementation.

---

### ✅ No Action — `DataHandler._compute()`: `sum(closes[-50:]) / 50` for SMA

```python
sma_today = sum(closes[-sma_period:]) / sma_period
sma_prior = sum(closes[-sma_period - 1:-1]) / sma_period
```

Python's `sum()` builtin is implemented in C and iterates over the list via the C array
protocol — approximately 10× faster than a manual `for` loop. At 50 elements this is
sub-microsecond and not a meaningful contributor to daily scan time. After C1 is applied,
`np.mean(closes[-50:])` is the consistent form, but the numerical difference is
immeasurable. This is a style choice, not a performance issue.

---

## Multiplier 2 — IPC (Instructions Per Clock)

**All handlers: ✅ No actionable issues**

- `entry_engine.py`, `exit_engine.py`, `regime_filter.py`, `risk_manager.py`,
  `pyramiding_manager.py` — all operate on small dicts of scalar comparisons with no
  accumulator loops of any kind.
- EMA scalar loop is a serial dependency chain by algorithmic necessity (see above).
- After C3 is applied, the ATR path uses `np.maximum` / `np.abs` — these are
  element-wise (no dependency chain), so ILP is exploited at the hardware level inside
  NumPy.

No programmer action required beyond the Waste fixes above.

---

## Multiplier 3 — SIMD

**Status: Available for free after C1 is applied**

Once `_extract()` returns `np.ndarray` (C1), every subsequent NumPy operation (`np.mean`,
`np.multiply`, `np.maximum`, `np.abs`) dispatches to platform SIMD (SSE2 / AVX2)
automatically. No additional work is required:

| Operation | SIMD-eligible after C1? |
|---|---|
| Dollar volume (C2) | ✅ `np.multiply(...).mean()` |
| ATR True Range (C3) | ✅ `np.maximum(...)` + `np.abs(...)` |
| EMA | ❌ Serial chain — scalar by design |
| SMA | ✅ `np.mean(closes[-50:])` if converted |

The only exception is EMA, which remains scalar by algorithmic necessity.

---

## Multiplier 4 — Caching

**Overall: ✅ Clean**

| Check | Status |
|---|---|
| Working set tier | L1 per-symbol (3.2 KB), L2–L3 full scan (640 KB) — no DRAM pressure |
| Memory access pattern | Sequential index 0→N through price arrays |
| `DataHandler._cache` | Keyed by `(str(symbol), date)` — O(1) lookup, cleared at scan start |
| 14-day universe cache | `_should_use_cache()` prevents re-sorting 8,000 coarse rows |
| `TradeRecord` leg sums | At most 4 legs; summing on access is effectively O(1) |

No cache-layer action required.

---

## Multiplier 5 — Multithreading

**Overall: N/A by design**

The 200-symbol scan is embarrassingly parallel, but the LEAN `history()` API is
single-threaded and blocking. Parallelisation requires a pre-fetch architectural change
that is out of scope for this assessment.

---

## Priority Stack

| Priority | ID | Issue | File / Method | Fix |
|---|---|---|---|---|
| 🔴 Critical | C1 | `_extract()` list comprehension × 5 cols × 200 symbols | [`data_handler.py`](../../handlers/data_handler.py) `_extract()` | Return `bars[col].values` (ndarray) on DataFrame path |
| 🔴 Critical | C2 | Dollar-volume Python generator with float coercions | [`data_handler.py`](../../handlers/data_handler.py) `_compute()` | `np.multiply(closes[-20:], volumes[-20:]).mean()` |
| 🔴 Critical | C3 | `_atr()` O(14) loop — ATR bars are fully independent | [`data_handler.py`](../../handlers/data_handler.py) `_atr()` | `np.maximum(hi-lo, np.abs(hi-pc), np.abs(lo-pc)).mean()` |
| ⚠️ Medium | M1 | `_force_include_regime()` string alloc per symbol | [`universe_filter.py`](../../handlers/universe_filter.py) | Set-based lookup; avoid `str + [item]` concatenation |
| ⚠️ Medium | M2 | `active_symbols` copies 200 items on every access | [`universe_filter.py`](../../handlers/universe_filter.py) | Return cached list directly; document no-mutation contract |
| ⚠️ Medium | M3 | `_submit_exit()` O(n) scan over `securities.keys` | [`main.py`](../../main.py) | Maintain `str→Symbol` dict built in `_evaluate()` |
| 🟢 Low | L1 | `close_trade()` recomputes leg sums 2–3× | [`position_manager.py`](../../handlers/position_manager.py) | Cache `total_quantity` / `avg_entry_price` as locals |
| ✅ No action | — | EMA scalar loop | [`data_handler.py`](../../handlers/data_handler.py) `_ema()` | Serial IIR — correct by design |
| ✅ No action | — | `sum(closes[-50:]) / 50` SMA | [`data_handler.py`](../../handlers/data_handler.py) | Python `sum()` runs in C; sub-µs at 50 elements |

---

## Review Summary

```
Implementation state: All 8 handlers fully implemented. No stubs or missing files.
                      Prior forward-looking prescriptions are now current findings.

Hot path:             _evaluate() → DataHandler._compute() × 200 symbols/day
Input size:           ~80 bars × 5 cols × 8 bytes = 3.2 KB/symbol → L1 ✅

Waste (Mult 1):       🔴 Three critical issues in data_handler (C1, C2, C3).
                         All stem from _extract() returning Python lists instead of
                         np.ndarray, forcing per-element CPython dispatch downstream.
                         Two medium issues in universe_filter (M1, M2) and one in
                         main (M3). One low issue in position_manager (L1).

IPC (Mult 2):         ✅ No actionable chains. ATR independence resolved by C3.
                         EMA serial chain is correct by design.

SIMD (Mult 3):        ✅ Free after C1 — NumPy dispatches to SSE2/AVX2 automatically.
                         No additional work required beyond the C1–C3 fixes.

Cache (Mult 4):       ✅ L1/L2 working set, sequential access, correct cache key design,
                         14-day universe caching prevents repeated sort.

Threading (Mult 5):   N/A — LEAN history() API is single-threaded.

Highest-priority action: Fix C1 (_extract → ndarray). C2 and C3 follow automatically
                          once closes/volumes/highs/lows are np.ndarray.
Expected gain vs. current: ~50–100× on the compute portion of the daily scan.
```
