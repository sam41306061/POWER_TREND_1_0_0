# Data Alignment Invariants

**Source:** `handlers/data_handler.py`
**Category:** data
**Invariant level:** MUST — tests enforce these rules

---

## Overview

All indicator computation in this algorithm flows through `DataHandler`, which abstracts
over two fundamentally different data representations: LEAN's DataFrame (from
`algorithm.history()`) and lists of bar objects (from test stubs in `type_stubs.py`).
The alignment rules here ensure consistent behavior across both paths.

---

## Dual-Format Support

`_extract_column(history, column)` handles:

1. **DataFrame path** (LEAN production): `history["close"]` — accesses by column name
2. **Bar list path** (test stubs): `[getattr(bar, column) for bar in history]`

The method tries the DataFrame path first and falls back to the bar-list path on `KeyError`
or `TypeError`. **Never bypass this method** to access history data directly.

---

## Column Name Convention

All column names are **lowercase**:

| Column | Meaning |
|---|---|
| `close` | Closing price |
| `high` | Session high |
| `low` | Session low |

LEAN DataFrames use lowercase column names when accessed via `history()` with `Resolution.DAILY`.
Test stubs must expose matching lowercase attributes.

---

## Date Alignment

- `DataHandler._today()` returns `algorithm.time.date()` (converted from `datetime` if needed).
- All cache keys use this date — never `datetime.now()` or wall-clock time.
- During backtesting, `algorithm.time` is the simulation time, not real time. This ensures
  cache invalidation is test-deterministic.

---

## Resolution

- All history fetches use `Resolution.DAILY` (imported from `AlgorithmImports`).
- Intraday data is **never** used for indicator computation in this strategy.
- The `DataHandler` does not manage consolidators — it reads pre-built daily bars only.

---

## Ordering Guarantee

- `_extract_column()` returns values in **oldest-to-newest** order (chronological).
- `closes[-1]` is always the most recent close.
- `closes[0]` is the oldest bar in the history window.
- ATR computation iterates `range(1, len(closes))` — index 0 has no prior bar for true range.

---

## Empty / Insufficient History Guards

1. If `history` is `None` → return `{}`
2. If `len(history) == 0` → return `{}`
3. If extracted `closes` list is empty → return `{}`
4. Any caller of `get_indicators()` must handle `{}` as a valid return (no `KeyError` risk).

---

## Lookback Sizing Rule

```python
lookback = config.SMA_50_PERIOD + 20   # currently 70 bars
```

This provides enough bars to:
- Compute SMA-50 with a full window
- Seed all EMAs (max period = 34) with sufficient history
- Compute ATR mean over 50 bars

Do not reduce this value without verifying that all indicators remain stable at warm-up.

---

## Market Regime Data

`get_market_regime_indicators(index_symbol)` is a delegating alias for `get_indicators()`.
SPY regime indicators use the **same cache** as equity indicators. SPY must be subscribed as
a data source in `main.py` for this to work in production.
