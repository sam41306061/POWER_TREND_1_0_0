# Indicator Caching Rules

**Source:** `handlers/data_handler.py`
**Category:** indicators
**Invariant level:** MUST — tests enforce these rules

---

## Overview

`DataHandler` is the single computation point for all technical indicators in this algorithm.
It provides a `(symbol, date)` keyed cache to prevent redundant history fetches within a single
scan cycle. Every handler that needs price data or indicators calls `DataHandler.get_indicators()`.

---

## Cache Key Structure

```python
cache_key = (str(symbol), today)   # today = algorithm.time.date()
```

- Key is a tuple of the **string form of the symbol** and the **current algo date** (not wall clock time).
- Cache is **never shared across days** — `clear_cache()` resets the entire dict.
- `get_market_regime_indicators(index_symbol)` delegates to `get_indicators()` and uses the
  same cache, so SPY regime indicators are also cached once per day.

---

## Invariants

1. **One API call per (symbol, date)** — if `cache_key` is in `self._cache`, return immediately
   without calling `self._algorithm.history()`.
2. **History injection for tests** — if the caller passes a `history=` argument, no API call is
   made regardless of cache state. Tests always use this path.
3. **Empty history guard** — if history is `None` or length-zero, return `{}` (empty dict).
   All callers must handle the empty-dict case without raising.
4. **Cache is cleared at the start of every scan cycle** — `main.py` calls
   `data_handler.clear_cache()` before `_scan_universe()`. Do not call it mid-cycle.

---

## Indicator Computation

`get_indicators()` returns:

```python
{
    "price":    float,   # closes[-1]
    "sma_50":   float,   # simple moving average, 50 periods
    "ema_8":    float,   # exponential moving average, 8 periods
    "ema_21":   float,   # exponential moving average, 21 periods
    "ema_34":   float,   # exponential moving average, 34 periods
    "atr_14":   float,   # average true range, 14 periods
    "atr_mean": float,   # rolling ATR mean over 50 periods
}
```

### EMA Seeding Rule
EMAs are seeded from the SMA of the first `period` closes, then apply the standard
alpha formula: `alpha = 2 / (period + 1)`. This matches QuantConnect's built-in EMA seeding.

### ATR Computation
- `atr_14` = mean of the last 14 true ranges
- `atr_mean` = mean of the last 50 true ranges (used for ATR extension checks)
- True range = `max(high-low, |high - prev_close|, |low - prev_close|)`

### Lookback Requirement
History fetch uses `SMA_50_PERIOD + 20` bars (currently 70 bars) as the lookback to ensure
SMA-50 has enough data at algorithm start.

---

## Period Constants (from `config.py`)

| Constant | Value |
|---|---|
| `SMA_50_PERIOD` | 50 |
| `EMA_8_PERIOD` | 8 |
| `EMA_21_PERIOD` | 21 |
| `EMA_34_PERIOD` | 34 |
| `ATR_PERIOD` | 14 |

---

## Column Extraction

`_extract_column()` handles both DataFrame-like objects (from LEAN history API) and lists of
bar objects (from test stubs). Never assume a specific type — always use this method.

---

## Common Failure Modes

- Returning cached stale data when `clear_cache()` is not called: scan sees yesterday's indicators
- Calling `get_indicators()` on a symbol that has no history in the test → returns `{}`;
  downstream code must guard with `if not indicators: continue`
- Passing a symbol as `Symbol` object vs. string: always `str(symbol)` for cache key consistency
