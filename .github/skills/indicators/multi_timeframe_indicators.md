# Multi-Timeframe Indicators

**Source:** QC Documentation (rag/data/doc_store.json — crawl_date: 2026-03-23),
`handlers/data_handler.py`
**Category:** indicators
**Status:** ✅ Populated — derived from scraped QC docs + handler source

---

## Overview

This strategy uses **manual indicator computation via `DataHandler`** rather than
QC's native auto-updating indicator primitives. This pattern is chosen for testability:
`DataHandler.get_indicators()` accepts an injected history DataFrame so unit tests
run without any LEAN platform calls.

---

## Native QC Indicator Registration (Auto-Update)

QC provides first-class indicator primitives that auto-update on new data:

```python
def initialize(self) -> None:
    self._symbol = self.add_equity("SPY").symbol

    # Auto-registers and updates on every on_data() call
    self._sma = self.sma(self._symbol, 20)
    self._ema = self.ema(self._symbol, 8)
    self._atr = self.atr(self._symbol, 14)

    # Warm-up using history injection (fills the indicator before start date)
    self.warm_up_indicator(self._symbol, self._sma)
```

After registration, `self._sma.current.value` returns the latest value in any callback.
The indicator is marked `.is_ready = False` until `period` bars have been consumed.

**Supported indicator methods (snake_case):** `sma()`, `ema()`, `atr()`, `bb()`, `rsi()`,
`macd()`, `stoch()` — see QC docs `/writing-algorithms/indicators/supported-indicators/`.

---

## Manual Computation via DataHandler (This Codebase)

`DataHandler` handles all indicator math internally using pandas-style list arithmetic
over history DataFrames. No QC indicator objects are created.

```python
# In main.py initialize():
self._data_handler = DataHandler(self)

# In scan loop:
history = self.history(symbol, 70, Resolution.DAILY)
indicators = self._data_handler.get_indicators(symbol, history=history)
#  → {"price": ..., "sma_50": ..., "ema_8": ..., "ema_21": ...,
#     "ema_34": ..., "atr_14": ..., "atr_mean": ...}
```

**Why manual over native?**
- Native indicators require a live `Symbol` subscription and LEAN platform context
- `DataHandler` accepts an injected `history` kwarg → fully testable in `pytest`
- Cache-aside by `(symbol, date)` prevents redundant `self.history()` calls within a day

---

## Requesting History Across Resolutions

```python
# Daily bars — most common for this strategy
history = self.history(symbol, 70, Resolution.DAILY)
# → DataFrame with columns: open, high, low, close, volume
# → Index: (symbol, datetime) MultiIndex

# Minute bars
history = self.history(symbol, 390, Resolution.MINUTE)

# Trailing time period (calendar days, not trading days)
history = self.history(symbol, timedelta(days=90), Resolution.DAILY)
```

The `timedelta` argument counts **calendar days** — weekends and holidays are included
in the count but produce no bars.

---

## Consolidators (Not Used in Current Strategy)

If intraday data is added later, use consolidators to build higher-resolution bars:

```python
from QuantConnect.Data.Consolidators import TradeBarConsolidator

# Aggregate 1-min bars into 15-min bars
consolidator = TradeBarConsolidator(timedelta(minutes=15))
consolidator.data_consolidated += self._on_15min_bar
self.subscription_manager.add_consolidator(symbol, consolidator)

def _on_15min_bar(self, sender, bar):
    self._sma.update(bar.end_time, bar.close)
```

This strategy uses **daily `Resolution.DAILY`** only — no consolidators are needed.
Consolidators are registered in `initialize()` alongside the source subscription.

---

## Weekly Bar Construction

For weekly bars, use a `CalendarConsolidator`:

```python
from QuantConnect.Data.Consolidators import TradeBarConsolidator
from QuantConnect import Calendar

consolidator = TradeBarConsolidator(Calendar.Weekly)
```

Weekly bars close on Friday at market close. **Universe timing caveat:** if universe
selection runs mid-week and a new symbol is added, the consolidator for that symbol
will have an incomplete bar until Friday.

---

## Multi-Symbol Indicator Management

When indicators are needed for each symbol in a dynamic universe, maintain a dict:

```python
self._indicators = {}   # {symbol: {"sma": sma_obj, "ema8": ema_obj}}

def on_securities_changed(self, changes):
    for security in changes.added_securities:
        sym = security.symbol
        self._indicators[sym] = {
            "sma": self.sma(sym, 50),
            "ema8": self.ema(sym, 8),
        }
        self.warm_up_indicator(sym, self._indicators[sym]["sma"])
    for security in changes.removed_securities:
        sym = security.symbol
        self._indicators.pop(sym, None)
        self.deregister_indicator(self._indicators[sym]["sma"])
```

This pattern is **not used** in `DataHandler` (which is stateless per call), but
applies if native QC indicators are introduced.
