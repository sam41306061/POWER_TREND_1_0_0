# Overfitting Prevention

**Source:** QC Documentation — Research Guide, `config.py`
**Category:** backtesting
**Status:** ✅ Populated — parameter detection, hypothesis-driven research, and safeguards

---

## Overview

Overfitting occurs when algorithm parameters are fine-tuned to fit historical data noise,
degrading performance on new data. QuantConnect provides a Research Guide panel with
overfitting indicators. This strategy with 107 symbols and multiple option chain filters
has inherent overfitting risk that must be actively managed.

---

## Hypothesis-Driven Research

Every modification to this algorithm must trace back to the central hypothesis:

> A change in **pre-earnings institutional buying pressure** leads to **stock appreciation
> and IV expansion in the 7–30 day window before confirmed earnings**.

If a code change is not driven by this thesis — e.g., adding a momentum filter because
it improved backtest returns — stop and return to thesis development.

### Cause and Effect Pattern

| Cause | Effect |
|---|---|
| Institutional pre-positioning before earnings | Stock price appreciation |
| Anticipated earnings volatility | IV expansion on near-dated options |
| Confirmed earnings date within 7–30 days | Actionable entry window |
| SMA-50 + EMA stack alignment | Uptrend confirmation reduces false entries |
| Exit before earnings announcement | Avoids IV crush and binary event risk |

---

## QC Research Panel Thresholds

QuantConnect tracks three overfitting indicators on every project:

### 1. Backtest Count

| Range | Risk Level |
|---|---|
| 0–30 backtests | Likely Not Overfit |
| 30–70 backtests | Possibly Overfitting |
| 70+ backtests | Probably Overfitting |

**Current project status:** 46 backtests completed. Approaching caution zone.

Each backtest performed on an idea moves it closer to being overfit — you are selecting
for strategies written into code instead of being based on the central thesis. Limit
backtests to parameter validation, not parameter discovery.

### 2. Parameter Count

| Range | Risk Level |
|---|---|
| 0–10 parameters | Likely Not Overfit |
| 10–20 parameters | Possibly Overfitting |
| 20+ parameters | Probably Overfitting |

**Current project status:** QC detects ~1,137 parameters (dominated by 107 × option chain
filter params). Unique meaningful parameters: ~175. The dominant contributor is the static
universe size (107 symbols × filter parameters per chain subscription), not hand-tuned
strategy constants.

**Mitigation:** Most "parameters" are structural (option chain subscriptions). True tunable
constants in `config.py` number approximately 15–20. Keep these minimal.

### 3. Research Time Invested

| Range | Risk Level |
|---|---|
| 0–8 hours | Likely Not Overfit |
| 8–16 hours | Possibly Overfitting |
| 16+ hours | Probably Overfitting |

**Guideline:** Within two full working days, a proficient coder should be able to
thoroughly test a single hypothesis. If you are spending weeks on parameter tuning,
you are likely overfitting.

---

## Parameter Detection — What QC Counts

QC scans code for these patterns and flags them as "parameters":

| Detection Criterion | Example in This Codebase |
|---|---|
| Numeric Comparison | `if days_to_earnings >= 7` → counted as parameter |
| TimeSpan / timedelta | `timedelta(days=30)` → counted |
| Order Event numeric args | `self.market_order(symbol, 10)` → `10` counted |
| Scheduled Event args | Time-of-day in `schedule.on()` → counted |
| Variable Assignment | `self._target_delta = 0.30` → counted |
| Mathematical Operation | `100 * contracts` → counted |
| LEAN API numeric args | `self.sma(symbol, 50)` → `50` counted |

### What QC Does NOT Count

| Exclusion | Example |
|---|---|
| Common APIs | `set_start_date(2020, 1, 1)` — excluded |
| Boolean comparison | `if is_ready:` — excluded |
| String numbers | `self.log(f"delta={delta}")` — excluded |
| Variable names with numbers | `sma_50` as variable name — excluded |
| Rounding / indexing | `round(x, 2)`, `arr[0]` — excluded |

---

## Overfitting Manifestations

| Pattern | Description | Risk in This Strategy |
|---|---|---|
| **Data Dredging** | Running many tests, only reporting significant results | Filtering 107 symbols to find the few that backtest well |
| **Hyper-Tuning Parameters** | Manually adjusting values to improve results | Tweaking `TARGET_DELTA`, `MIN_CALENDAR_DAYS_TO_EARNINGS`, etc. |
| **Overfit Regression Models** | Too many variables in statistical models | Not applicable (rule-based strategy) |
| **Stale Testing Data** | Not changing test data between iterations | Always using same date range for backtests |

---

## Out-of-Sample Period

Organization managers can enforce backtests end N months before current date.

**Recommended practice for this strategy:**
- Reserve the most recent 3–6 months of data as out-of-sample
- Develop on historical period → validate on hold-out period
- Only deploy to live trading if out-of-sample performance confirms in-sample results

To configure: Organization Homepage → Backtesting Out of Sample Period → set duration.

---

## Invariants

1. **All tunable constants must live in `config.py`** as `Final` typed values — never hardcode
   thresholds in handler code. This makes the true parameter count auditable.
2. **Do not add parameters to improve backtest results** — only add parameters that are
   justified by the central hypothesis (pre-earnings buying pressure → stock appreciation + IV expansion).
3. **Log which gate blocked each symbol** — if you modify gate thresholds based on
   "symbols that should have been traded", you are data dredging.
4. **Walk-forward validation** — parameter optimization should use walk-forward methodology,
   not in-sample optimization on the full date range.
5. **Track backtest count** — the project is at ~46 backtests. Each incremental backtest
   should test a specific hypothesis, not explore parameter space.
6. **Universe selection is not a parameter to tune** — the 107-symbol universe in
   `earnings_candidates.csv` is based on fundamental criteria, not backtest performance.
