# Option Chain Filtering

**Source:** `handlers/instrument_selector.py`, `handlers/option_analytics.py`
**Category:** options
**Invariant level:** MUST — tests enforce these rules

---

## Overview

`InstrumentSelector` selects the specific option contract to trade from the full options
chain. `OptionAnalytics` provides the IV and delta calculations that gate entry and inform
rolling decisions. Together they define the exact contract selection and analytics layer.

---

## Contract Selection Flow (`InstrumentSelector`)

```
option_chain(symbol)
    │
    ├── Filter: calls only (Right == "Call" | "C", case-insensitive)
    ├── Filter: OpenInterest >= MIN_OPEN_INTEREST_MULTIPLIER * FIXED_CONTRACTS
    ├── Filter: bid/ask spread <= _MAX_BID_ASK_SPREAD (0.50, not yet in config)
    │
    └── Rank: closest delta to TARGET_DELTA
            └── Return best match
```

---

## Delta Target by Trade Type

| Trade Type | Target Delta | Fallback |
|---|---|---|
| `"DEFAULT_SETUP"` | `TARGET_DELTA = 0.30` | Delta 40–70 if 0.30 unavailable |
| `"CONSERVATIVE"` | Delta 40–70 range | None |

The `_find_closest_delta_strike()` method always selects the contract with `abs(delta - target)`
minimised — there is no band filter, just a proximity sort.

---

## Open Interest Gate

```python
OpenInterest >= MIN_OPEN_INTEREST_MULTIPLIER * FIXED_CONTRACTS
# currently: 100 * 10 = 1000 contracts minimum OI
```

- `FIXED_CONTRACTS = 10` (contracts per position)
- `MIN_OPEN_INTEREST_MULTIPLIER = 100`
- OI is checked via `getattr(contract, "OpenInterest", getattr(contract, "open_interest", 0))`
  to support both LEAN contract objects and test stubs

---

## Bid/Ask Spread Gate

```python
_MAX_BID_ASK_SPREAD = 0.50  # lives inside instrument_selector.py, not config yet
spread = ask_price - bid_price
```

When `require_live_quotes=False` (used in pre-market scans), this gate is skipped.

---

## Weekly Options Check

`has_weekly_options(symbol)` checks whether `algorithm.option_chain(symbol)` returns any
contracts at all. Returns `bool`. Used in Phase 1 validation via `SetupChecker`.

---

## Delta Extraction

`_get_delta(contract)` is order-of-priority:
1. `contract.Greeks.Delta` (LEAN production object)
2. `contract.delta` (test stub attribute)
3. Returns `abs()` of whichever is found — always positive

---

## IV Analytics (`OptionAnalytics`)

### `get_implied_volatility(symbol)`
- Reads from `algorithm.iv_data` dict (injectable test slot)
- Returns `float` as a percentage (e.g., `25.5` for 25.5%)
- Returns `0.0` if no data available

### `compare_iv_vs_rolling_average(symbol, days=30)`
- Reads from `algorithm.iv_history` dict (injectable test slot)
- Returns `current_iv / rolling_avg`; returns `1.0` if no history
- A ratio of `1.5` means IV is 150% of its 30-day average

### `is_iv_already_elevated(symbol, surge_threshold=150.0)`
- Returns `True` if `ratio * 100 >= surge_threshold`
- Default threshold: `150.0` (IV must not already be 1.5× normal)
- Used by `SetupChecker` Phase 1 gate to prevent entering after IV has pre-expanded

---

## Delta Estimation (`OptionAnalytics.estimate_delta`)

Uses a simplified Black-Scholes approximation:
- Inputs: `strike`, `dte`, `iv` (as decimal), `current_price`
- Uses `scipy.stats.norm.cdf` / internal N(d1) calculation
- Risk-free rate assumed `0.05` (5%) — hardcoded in the method
- For Delta-20 targeting, the chain is queried live rather than estimated;
  `estimate_delta` is used for validation and analytics only

---

## IV Cache

`OptionAnalytics._iv_cache` stores `{symbol: iv_value}` for the current scan cycle.
It is **not shared** with `DataHandler._cache` — they are separate caches.
IV cache is not explicitly cleared; it is re-populated on each algorithm instantiation.

---

## OptionFilterUniverse — set_filter API

**Source:** QC docs (`equity-options/requesting-data/universes`, `equity-options/handling-data`)

`option.set_filter(lambda u: ...)` controls which contracts LEAN subscribes to and includes
in `option_chains`. It is called once at subscription time (in `on_securities_changed()`).

### Verified working methods (from RAG data)

```python
# Expiration window (MOST COMMON — what this strategy uses)
option.set_filter(lambda u: u.expiration(min_days, max_days))

# Delta range + expiration
option.set_filter(lambda u: u.delta(0.2, 0.6).expiration(0, 30))

# Calls only by contract type filter
option.set_filter(lambda u: u.expiration(0, 30).calls_only())

# Strikes around ATM
option.set_filter(lambda u: u.strikes(-5, +5).expiration(0, 30))
```

### This strategy's filter (main.py on_securities_changed)

```python
option.set_filter(
    lambda u: u.expiration(
        MIN_CALENDAR_DAYS_TO_EARNINGS,     # 7
        MAX_CALENDAR_DAYS_TO_EARNINGS + 15, # 45
    )
)
```

The `+15` buffer ensures a Friday expiry is always present at the far edge of the
7–30 day entry window. Weekly Friday selection is **not** done here — it's done
post-subscription by `InstrumentSelector._get_weekly_expiry_for_earnings()`, which
checks `expiry.weekday() == 4`.

### Methods that do NOT exist in LEAN's OptionFilterUniverse

| Hallucinated call | Correct alternative |
|---|---|
| `u.weeklys()` | Remove entirely — use `expiration()` window to cover weeklies |
| `u.weeklys_only()` | No direct equivalent; filter by expiry date in `InstrumentSelector` |

### Required: RAW data normalization

When using `add_option()` with a universe filter, the underlying equity must use raw prices
so that strike prices and underlying prices are comparable:

```python
spy = self.add_equity("SPY", data_normalization_mode=DataNormalizationMode.RAW).symbol
```

For universe-mode strategies using `ManualUniverseSelectionModel`, set this via
`universe_settings.data_normalization_mode = DataNormalizationMode.RAW` in `initialize()`.

---

## Theta Tracking

`OptionAnalytics` tracks daily time decay (theta) for positions held by `PositionManager`.
Theta is read-only analytics — it does not trigger any exit condition directly.
Exits based on DTE are handled through `PositionManager.check_exit_conditions()` via the
earnings proximity date check, not a raw DTE threshold.
