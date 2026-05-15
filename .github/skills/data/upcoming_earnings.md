# Upcoming Earnings Dataset

**Source:** QC Documentation (rag/data/doc_store.json — crawl_date: 2026-05-04), EODHD  
**Category:** data  
**Status:** ✅ Populated — derived from scraped QC docs

---

## Overview

The **Upcoming Earnings** dataset, provided by EOD Historical Data (EODHD), is a daily universe of US Equities with an earnings report publication in the **upcoming 7 days**.

| Property | Value |
|---|---|
| Start Date | January 1998 |
| Data Density | Sparse |
| Resolution | Daily |
| Timezone | New York |

Accuracy vs Nasdaq benchmark:
- **96.79%** capture rate of scheduled earnings reports
- **97.25%** exact-date precision
- **99.28%** precision within ±3 days
- Also includes unscheduled / special earnings reports

---

## Dataset Class

```python
EODHDUpcomingEarnings
```

Primary use case: **universe selection**. Can also be used as a standalone `add_data` source.

---

## Data Point Attributes

| Attribute | Type | Description |
|---|---|---|
| `symbol` | `Symbol` | Equity symbol for the reporting company |
| `report_date` | `datetime` | Scheduled earnings report date |
| `report_time` | `EODHD.ReportTime` | When during the day earnings are reported |
| `estimate` | `decimal` | Estimated EPS for the upcoming report |
| `value` / `price` | `decimal` | Representative value for this data point |

### `ReportTime` Enum

| Value | Meaning |
|---|---|
| `EODHD.ReportTime.BEFORE_MARKET` | Reported before market open |
| `EODHD.ReportTime.AFTER_MARKET` | Reported after market close |

---

## Universe Selection

Primary usage pattern — add as a universe filter:

```python
def initialize(self) -> None:
    self._universe = self.add_universe(EODHDUpcomingEarnings, self.universe_selection_filter)

def universe_selection_filter(self, earnings: List[EODHDUpcomingEarnings]) -> List[Symbol]:
    return [d.symbol for d in earnings if d.report_date <= self.time + timedelta(3) and d.estimate > 0]
```

Key filter patterns:
- `d.report_date <= self.time + timedelta(N)` — limit to earnings within N days
- `d.estimate > 0` — only include stocks with a positive EPS estimate
- `d.report_time == EODHD.ReportTime.BEFORE_MARKET` — filter by report timing

---

## Requesting as Standalone Data

```python
def initialize(self) -> None:
    self._symbol = self.add_equity("AAPL", Resolution.DAILY).symbol
    self._dataset_symbol = self.add_data(EODHDUpcomingEarnings, "earnings").symbol
```

---

## Accessing Data in `on_data`

### Single symbol lookup

```python
def on_data(self, slice: Slice) -> None:
    upcoming = slice.get(EODHDUpcomingEarnings).get(self._symbol)
    if upcoming:
        self.log(f"{self._symbol} reports at {upcoming.report_date} {upcoming.report_time}, est EPS {upcoming.estimate}")
```

### Iterate all earnings in slice

```python
def on_data(self, slice: Slice) -> None:
    for equity_symbol, data_point in slice.get(EODHDUpcomingEarnings).items():
        self.log(f"{equity_symbol} reports at {data_point.report_date} {data_point.report_time}, est EPS {data_point.estimate}")
```

---

## Integration with `no_earnings` Gate

This strategy's setup checker enforces a `no_earnings` gate using `EARNINGS_LOOKBACK_DAYS = 14`. The EODHD dataset can directly supply `report_date` for this check:

```python
# Example: check no earnings within the next 14 days
upcoming = slice.get(EODHDUpcomingEarnings).get(symbol)
if upcoming and upcoming.report_date <= self.time + timedelta(14):
    return False  # block entry — earnings too close
```

See [bounce_setup_validation.md](../trading/bounce_setup_validation.md) for the full gate context.

---

## Universe Settings for Options Strategies

When using with options, add these settings in `initialize()`:

```python
self.settings.seed_initial_prices = True          # needed for option chain filtering at universe join
self.universe_settings.resolution = Resolution.DAILY
self.universe_settings.data_normalization_mode = DataNormalizationMode.RAW  # required for strike price comparisons
```

---

## Historical Data

Retrieve historical dataset records across all universe members:

```python
history = self.history(EODHDUpcomingEarnings, timedelta(100), Resolution.DAILY)
```

Retrieve for a specific known symbol:

```python
history = self.history[EODHDUpcomingEarnings](timedelta(100), Resolution.DAILY).loc[self._symbol]
```

If no data exists in the requested period the result is empty — always guard before iterating.

---

## Removing the Subscription

To remove the dataset subscription (e.g. when tearing down a position or universe):

```python
self.remove_security(self.dataset_symbol)
```

---

## Example Applications

- **Long straddle on upcoming earnings** — enter 5 days before the report date to capture volatility build-up; close 1 day after announcement.
- **Earnings avoidance filter** — exclude universe members whose `report_date` falls within the next N days.
- **Positive-estimate long bias** — hold only stocks where `d.estimate > 0`.

---

## Notes

- Dataset is **daily resolution only** — not tick or minute.
- `Slice` may not contain data for every symbol at every time step — always guard with `if upcoming:`.
- The dataset covers **unscheduled special earnings** in addition to scheduled reports.
- Data density is **sparse** — many days will have no new data points for a given symbol.
