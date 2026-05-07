# Consolidation Rules

**Source:** QC Documentation (rag/data/doc_store.json — crawl_date: 2026-03-23),
`handlers/data_handler.py`
**Category:** data
**Status:** ✅ Populated — derived from scraped QC docs + handler source

---

## Overview

This strategy uses **daily `Resolution.DAILY`** data exclusively. No consolidators are
currently active. This document records consolidator patterns for future reference if
intraday data is added, and documents `DataNormalizationMode` rules that affect equity
and options pricing.

---

## TradeBarConsolidator

Aggregates lower-resolution bars into higher-resolution bars on a fixed time period:

```python
from QuantConnect.Data.Consolidators import TradeBarConsolidator

# Aggregate minute bars into 30-minute bars
consolidator = TradeBarConsolidator(timedelta(minutes=30))
consolidator.data_consolidated += self._on_consolidated_bar
self.subscription_manager.add_consolidator(self._symbol, consolidator)

def _on_consolidated_bar(self, sender, bar: TradeBar) -> None:
    # bar.time = open of bar; bar.end_time = close of bar
    self._sma.update(bar.end_time, bar.close)
```

**Consolidators must be registered in `initialize()`** alongside the source security.
They are automatically disposed when the algorithm ends.

---

## QuoteBarConsolidator

Used for **options and forex**, which emit `QuoteBar` (bid/ask) rather than `TradeBar`:

```python
from QuantConnect.Data.Consolidators import QuoteBarConsolidator

consolidator = QuoteBarConsolidator(timedelta(minutes=5))
consolidator.data_consolidated += self._on_option_bar
self.subscription_manager.add_consolidator(self._option_symbol, consolidator)
```

For equity options in daily resolution, `QuoteBar` data is received via
`slice.quote_bars[option_symbol]`, not a consolidator.

---

## Calendar Consolidators

Produce bars aligned to calendar boundaries (weekly, monthly):

```python
from QuantConnect.Data.Consolidators import TradeBarConsolidator
from QuantConnect import Calendar

# Weekly bars closing on Friday
weekly_consolidator = TradeBarConsolidator(Calendar.Weekly)

# Monthly bars closing on last trading day of month
monthly_consolidator = TradeBarConsolidator(Calendar.Monthly)
```

**Timing caveat:** If universe selection adds a new symbol mid-period, the consolidator
for that symbol will accumulate an incomplete bar until the boundary is reached.
Indicators updating from consolidator output may show stale or partial values.

---

## Data Normalization

`DataNormalizationMode` controls how splits and dividends adjust historical price data.
This is critical for correct SMA-50 and EMA values over long lookback windows.

```python
equity = self.add_equity("AAPL", Resolution.DAILY)
equity.set_data_normalization_mode(DataNormalizationMode.ADJUSTED)   # default
```

| Mode | Behaviour |
|---|---|
| `ADJUSTED` (default) | Prices back-adjusted for splits and dividends — SMA/EMA correct over time |
| `RAW` | No adjustment — price gaps at split/dividend dates corrupt MAs |
| `SPLIT_ADJUSTED` | Split-adjusted only, no dividend adjustment |
| `TOTAL_RETURN` | Includes dividend reinvestment |

**For this strategy:** use `ADJUSTED` (default). Earnings candidates have long price
histories; `RAW` mode would corrupt `SMA_50` values around split dates.

**Options implication:** When the underlying uses `ADJUSTED`, QC adjusts option strikes
and Greeks to match. Keep underlying and option normalization modes consistent.

---

## History Request Alignment

When `DataHandler` calls `self._algorithm.history(symbol, lookback, Resolution.DAILY)`:
- Returns a DataFrame with MultiIndex `(symbol, datetime)`
- Columns: `open`, `high`, `low`, `close`, `volume`
- Rows are ordered **chronologically** (oldest first)
- The last row `.iloc[-1]` is the most recent available bar
- `datetime` in the index is in the **algorithm time zone** (default: New York)

```python
history = self.history(symbol, 70, Resolution.DAILY)
# history.index.get_level_values(1)[-1] → most recent bar timestamp
closes = history["close"].tolist()   # chronological list
```

---

## Current Strategy Data Usage

| Data Type | Resolution | Source | Normalization |
|---|---|---|---|
| Equity bars (OHLCV) | Daily | `history()` API called in `DataHandler` | ADJUSTED |
| Option chain | Daily | `option_chain(symbol)` | N/A |
| SPY (regime filter) | Daily | `history()` via `DataHandler` | ADJUSTED |
