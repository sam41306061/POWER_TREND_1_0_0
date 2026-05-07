# Indicator Readiness Gates

**Source:** QC Documentation (rag/data/doc_store.json — crawl_date: 2026-03-23),
`handlers/data_handler.py`
**Category:** indicators
**Status:** ✅ Populated — derived from scraped QC docs + handler source

---

## Overview

Every QC indicator has an `.is_ready` property that is `False` until enough bars have
been consumed to produce a valid result. For manually-computed indicators (this codebase),
the equivalent gate is checking whether `DataHandler.get_indicators()` returned a non-empty
dict. Do not trade on an empty dict.

---

## IsReady Property (Native QC Indicators)

```python
if not self._sma.is_ready:
    return   # Indicator not ready — insufficient bars

value = self._sma.current.value   # Safe to read
```

**Bars required:**
| Indicator | Min bars before `is_ready = True` |
|---|---|
| `SMA(period=50)` | 50 bars |
| `EMA(period=8)` | 8 bars (approximate — EMA seeds faster than SMA) |
| `EMA(period=21)` | 21 bars |
| `ATR(period=14)` | 14 bars |

Attempting to read `.current.value` before `is_ready` returns `0` — it **does not raise**.
This is a silent failure; always guard with `is_ready`.

---

## Warm-Up and Indicators

`set_warm_up()` combined with `warm_up_indicator()` pre-seeds native QC indicators before
the backtest start date:

```python
def initialize(self) -> None:
    self._sma = self.sma(self._symbol, 50)
    self.warm_up_indicator(self._symbol, self._sma)   # feeds 50+ history bars
    self.set_warm_up(70)                               # feeds on_data for 70 bars
```

`warm_up_indicator` makes an internal history request and feeds bars directly into
the indicator — it does **not** require `set_warm_up` to operate.

`set_warm_up` controls the `is_warming_up` flag; during warm-up, `on_data` fires but
`market_order()` calls are blocked. Indicators registered for auto-update **do**
update during warm-up.

---

## History Injection Pattern (This Codebase)

`DataHandler` uses history injection instead of native QC indicator registration.
This bypasses the `is_ready` lifecycle entirely:

```python
# In scan: fetch history, pass to DataHandler
history = self.history(symbol, lookback, Resolution.DAILY)
indicators = self._data_handler.get_indicators(symbol, history=history)

# ALWAYS guard the return value
if not indicators:
    continue    # Insufficient history — skip this symbol
```

`get_indicators()` returns `{}` when:
- `history` is `None` or empty DataFrame
- Fewer bars available than needed for SMA-50 computation

The handler caches results by `(str(symbol), date)` — once computed for today it is
returned from cache without re-computing.

---

## Minimum Bar Requirements (This Strategy)

```python
lookback = config.SMA_50_PERIOD + 20   # = 70 bars
```

| Indicator | Period | Bars Available After Lookback |
|---|---|---|
| `sma_50` | 50 | 70 — fully seeded (20 surplus) |
| `ema_8` | 8 | 70 — well seeded |
| `ema_21` | 21 | 70 — fully seeded |
| `ema_34` | 34 | 70 — fully seeded (36 surplus) |
| `atr_14` | 14 | 70 — fully seeded |

If fewer than `lookback` daily bars exist for a symbol (e.g., recent IPO), `get_indicators()`
returns `{}` — the symbol is silently skipped by all phase gates.

---

## indicator_history() Method (Native)

QC also provides `indicator_history()` for fetching and updating an indicator with
historical data in one call:

```python
history = self.indicator_history(self._sma, self._symbol, 50, Resolution.DAILY)
# → resets indicator, makes history request, updates with historical bars
# → returns DataFrame with indicator values over the period
```

This is equivalent to the `warm_up_indicator` pattern but performs a reset first,
making it useful for re-seeding mid-algorithm.
