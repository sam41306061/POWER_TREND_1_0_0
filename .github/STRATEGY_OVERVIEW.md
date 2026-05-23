# Power Trend Algo 1 — Strategy Overview

> Status: **Implementation complete through Phase 6. Phase 7 (backtest writeup) pending.**
> Vehicle for execution: long US equities. QQQ is the regime gate, not a tradable.

---

## What This Strategy Does

**Core concept:** Identify "Power Trends" (Mike Webster style) on the **NASDAQ
proxy QQQ** and only allow long entries while QQQ is in an active trend.
Within that regime, trade a dynamic universe of liquid US equities using a
simplified pullback-and-continuation entry, scaling in via equal-size
pyramid adds.

**Position:** Long common stock (cash equity, no options, no leverage).

**Universe:** Top **200** US equities by 20-day average dollar volume,
filtered to `price ≥ $20` and `20d avg $ volume ≥ $50M`. Refreshed
**every 2 weeks**.

**Holding period:** Trend-following — open-ended. Positions live until a
per-stock exit rule fires. The QQQ regime turning off does **not** force
exits; it only suspends new entries.

**Why it works:**
1. Trend persistence in major indices is empirically real over multi-month windows.
2. Restricting entries to a confirmed Power Trend on QQQ filters out chop and bear regimes.
3. Pyramiding into proven leaders compounds capital where the edge is strongest.

**What kills it:**
- Sharp regime reversals (gap-down failures right after Power Trend activation).
- Choppy "twisty rope" markets where MAs cross repeatedly.
- Concentration in mega-cap tech via the dollar-volume ranking (a known bias).

### Volume policy

Raw share volume is **not** a trading signal anywhere in v1. Per the source material,
share-volume spikes are too noisy to trade off directly (a true distribution-day
classifier needs bar spread, close-in-range, prior-day context, and dollar volume —
see [Out of Scope](#out-of-scope-future-extensions)).

Volume enters the strategy in exactly **one** place: as **20-day average dollar
volume** in the universe ranking (`MIN_DOLLAR_VOLUME` floor + top-N sort). It is
never consulted as an entry, exit, or confirmation signal.

---

## Architecture

`main.py` is the only LEAN-aware module. All logic lives in pure-Python
handlers under `handlers/`. A single daily callback at market open drives
the pipeline.

### Handler responsibilities

| Handler | Responsibility |
|---|---|
| `handlers/universe_filter.py` | QC coarse-filter callback: liquidity floor → top-200 by 20d $-vol → 14-day cache. Force-includes QQQ. |
| `handlers/data_handler.py` | Compute & cache per `(symbol, date)`: `close`, `open`, `high`, `low`, `prior_close`, `prior_low`, `EMA21`, `SMA50`, `SMA10`, `prior_EMA21`, `prior_SMA50`, `dollar_volume_20d`, `atr_14`, `atr_50`, `atr_stretch_low` (= `(low - EMA21) / atr_50`), `high_vs_ema21` (= `(EMA21 - high) / atr_50`), `high_vs_sma10` (= `(high - SMA10) / atr_50`), `is_blue_bar` (= `close >= open`). |
| `handlers/regime_filter.py` | Power Trend rolling-counter state machine on QQQ only. Exposes `entries_allowed() -> bool` and `current_state -> {TREND_UP, NO_TREND, TREND_END}`. |
| `handlers/entry_engine.py` | Per-stock initial + add-on entry rules; gated by `regime.entries_allowed()`. |
| `handlers/pyramiding_manager.py` | Equal-size leg sizing; caps adds at `PYRAMID_MAX_ADDS`. |
| `handlers/exit_engine.py` | Per-stock priority-ordered exits: SMA breakdown, EMA cross, weakness, stop loss, account drawdown. |
| `handlers/risk_manager.py` | Tracks high-water-mark equity; suspends new entries when account drawdown > `MAX_ACCOUNT_DRAWDOWN_PCT`. |
| `handlers/position_manager.py` | Multi-leg avg-cost tracking: `legs`, `total_quantity`, `avg_entry_price`, `leg_count`, `last_leg_date`. |
| `handlers/setup_checker.py`, `technical_validator.py`, `instrument_selector.py`, `option_analytics.py` | **Delete** — not used by Power Trend. |

### Daily lifecycle (`_evaluate()` at `DAILY_EVAL_TIME`)

```
1. Refresh QQQ indicators → regime_filter.update(qqq_indicators)
2. For each open position:
   2a. exit_engine.check_partial(trade, indicators)
           → if high_vs_sma10 >= WEBBY_RSI_STRETCH_LEVEL: sell PARTIAL_EXIT_TRIM_FRACTION; skip full-exit check this bar
   2b. exit_engine.check(trade, indicators) — close entire position if any rule fires
3. If regime.entries_allowed() AND risk.is_new_entry_allowed():
       For each symbol in active universe (excluding QQQ):
           indicators = data_handler.get_indicators(symbol)
           If position open: try add-on (pyramiding) entry rule
           Else:             try initial entry rule
           If signal AND under MAX_POSITIONS_OPEN: submit market order
4. on_order_event → position_manager.add_leg() / reduce_position() / close_trade()
```

---

## Power Trend Definition (applied to QQQ only)

Webster's published Power Trend has **four** strict activation rules. All four
must be true on the same bar to flip the regime to `TREND_UP`:

1. `days_low_above_ema21 ≥ 10` — QQQ's daily low has held above the 21-day EMA
   for at least 10 consecutive sessions.
2. `days_ema21_above_sma50 ≥ 5` — the 21-day EMA has been above the 50-day SMA
   for at least 5 consecutive sessions.
3. `sma50_rising` — today's 50-day SMA > yesterday's 50-day SMA.
4. `is_blue_bar` — the activation bar itself closes at or above its open
   (`close ≥ open`). Webster calls this the "blue bar" requirement: an
   activation that prints a red bar is treated as suspect.

Stateful counters updated once per trading day from QQQ indicators:

- `days_low_above_ema21`: incremented when `today.low > today.EMA21`; reset to 0 otherwise.
- `days_ema21_above_sma50`: incremented when `today.EMA21 > today.SMA50`; reset to 0 otherwise.
- `sma50_rising`: `today.SMA50 > yesterday.SMA50`.
- `is_blue_bar`: `today.close ≥ today.open`.

State machine (four states; matches Webster's two-stage deactivation plus the
market-school `TREND_PRESSURE` extension):

| From | To | Condition |
|---|---|---|
| `NO_TREND` | `TREND_UP` | All four activation rules above are true on the same bar |
| `TREND_UP` | `TREND_PRESSURE` | QQQ `close < SMA50` (first break of the 50-day) while `EMA21 > SMA50` (only if `ENABLE_TREND_PRESSURE` is True) |
| `TREND_UP` ∨ `TREND_PRESSURE` | `TREND_END` | `EMA21 < SMA50` (the official cross-back) |
| `TREND_PRESSURE` | `TREND_UP` | QQQ `close > EMA21` AND `EMA21 > SMA50` (re-arm) |
| `TREND_END` | `NO_TREND` | Next bar (terminal label exists for one bar; immediate re-activation allowed when activation rules re-fire) |

**Only `TREND_UP` allows new entries.** During `TREND_PRESSURE` the regime is
"under pressure" — new entries are paused but existing positions are not
force-closed. `TREND_END` blocks new entries as well.

**No invented weakness/distribution rule.** The transcript discounts
distribution-day counting as too noisy and uses price-vs-21-day plus the
50-day cross as the primary signals. Distribution-day overlay is
[Out of Scope](#out-of-scope-future-extensions) for v1.

**Re-activation policy**: no cooldown. If the activation rules re-fire after
a deactivation, the regime returns to `TREND_UP` immediately.

### Lite mode (Webster's personal relaxations)

Webster has stated he personally trades a relaxed version of the four-rule
definition. The strict rules are the **default** and what backtests publish
against, but three boolean toggles let us A/B-test the lite variant without
branching the codebase:

| Toggle | Default | Effect when `False` |
|---|---|---|
| `REQUIRE_SMA50_RISING` | `True` | Drops rule 3 — allows activation while the 50-day SMA is flat or slightly down. |
| `REQUIRE_ACTIVATION_UPDAY` | `True` | Drops rule 4 — allows activation on a red bar. |
| `ENABLE_TREND_PRESSURE` | `True` | Skips the `TREND_PRESSURE` intermediate state — `TREND_UP` transitions directly to `TREND_END` on the EMA/SMA cross. |

Walk-forward must include comparison runs with each toggle individually
flipped and with all three flipped together ("full lite"). See
[Backtesting Plan](#backtesting-plan).

---

## Per-Stock Entry Rules

The full Power Trend classifier is **not** run per stock — only on QQQ.
This matches the source material: Webster classifies the *index*, then
relaxes per-stock buy criteria while the regime is on ("during a Power
Trend you can buy a stock whose low gets back above its 21-day without
waiting for a follow-through day"). The simplified per-stock trigger
below is the encoded form of that relaxation.

Confirmation uses Webster's **"blue bar"** rule — the entry day must be
flat or up (`close >= open`). The blue-bar requirement applies to the
per-stock entry bar **independently** of the regime's activation-bar
blue-bar rule (rule 4 above). Both checks read the same
`is_blue_bar = close >= open` field on `data_handler` output but evaluate
it on different symbols (QQQ for activation, the candidate stock for entry).

### Initial entry


```
regime.entries_allowed()                       # QQQ in TREND_UP
AND risk.is_new_entry_allowed()                # account DD gate
AND under MAX_POSITIONS_OPEN
AND not has_position(symbol)
AND price > EMA21 > SMA50                      # bullish stack
AND prior_low <= prior_EMA21                   # pullback touched the EMA21
AND close >= open                              # blue bar (per-stock)
```

### Webby RSI (Really Simple Indicator 2.0)

Webster's Webby RSI quantifies **how far price is from its 21-day EMA**,
normalised by the **50-period ATR** so readings are directly comparable
across instruments (slow Costco vs high-velocity growth stocks) and across
volatility regimes. It has three components:

#### Component 1 — `atr_stretch_low` (low vs EMA21, bullish histogram)

```
atr_stretch_low = (today.low - today.EMA21) / today.atr_50
```

Positive when the day's low is above the EMA21. A sustained "wall of blue"
(0.5–3.0 ATRs over many consecutive bars) is the primary visual signal of a
healthy trend. Values approaching **3 ATRs** indicate stretch — likely to
mean-revert; begin locking in partial gains and be cautious with new adds.

Early in a new Power Trend, `atr_stretch_low` reaching ~2–3 ATRs confirms
real momentum. Trends that never produce a meaningful wall of blue tend to
fail quickly.

In v1, `atr_stretch_low` is **computed and logged but not used as an entry gate**.
The binary `prior_low <= prior_EMA21` check is the entry trigger.

#### Component 2 — `high_vs_ema21` (high vs EMA21, bearish pressure)

```
high_vs_ema21 = (today.EMA21 - today.high) / today.atr_50
```

Positive when the day's *high* fails to reach the EMA21 from below — the bar
is living entirely below the moving average (bearish pressure). Diagnostic
only in v1; not used as an entry or exit gate.

#### Component 3 — `high_vs_sma10` (high vs SMA10, stretch/trim signal)

```
high_vs_sma10 = (today.high - today.SMA10) / today.atr_50
```

Measures how far the day's high extends above the 10-day simple MA.
At **≥ 3 ATRs** (`WEBBY_RSI_STRETCH_LEVEL`) this triggers a **stretch-trim
partial exit** — see [Exit Rules](#exit-rules-per-stock-priority-order).

#### ATR windows

| Field | ATR period | Config constant | Purpose |
|---|---|---|---|
| `atr_14` | 14 | `ATR_PERIOD` | Stop-loss sizing |
| `atr_50` | 50 | `WEBBY_RSI_ATR_PERIOD` | Webby RSI normalisation |

### Add-on (pyramid) entry

```
regime.entries_allowed()
AND has_position(symbol)
AND leg_count < PYRAMID_MAX_ADDS
AND a NEW pullback occurred since last leg     # prior_low <= prior_EMA21 after last_leg_date
AND close >= open                              # blue bar (per-stock)
```

### Sizing

Equal-size legs:
```
shares_per_leg = floor( INITIAL_LEG_SIZE_PCT * portfolio_value / current_price )
```

Maximum total per position = `INITIAL_LEG_SIZE_PCT * (1 + PYRAMID_MAX_ADDS)` of portfolio value (e.g., 25% × 4 = 100% in a max-size single name — gated in practice by `MAX_POSITIONS_OPEN`).

---

## Exit Rules (per stock, priority order)

The stretch-trim partial (Priority 0) is checked first each bar. If it fires,
full-exit rules (Priorities 1–4) are **skipped for that bar**.

| Priority | Type | Rule | Exit reason |
|---|---|---|---|
| 0 | **Partial** | `high_vs_sma10 ≥ WEBBY_RSI_STRETCH_LEVEL (3.0)` → sell `PARTIAL_EXIT_TRIM_FRACTION` (50%) of shares | `EXIT_REASON_STRETCH_TRIM` |
| 1 | Full | Account drawdown ≥ `MAX_ACCOUNT_DRAWDOWN_PCT` (15%) | `EXIT_REASON_DRAWDOWN` |
| 2 | Full | Stop loss: `current_price ≤ avg_entry_price * (1 - STOP_LOSS_PCT)` | `EXIT_REASON_STOP_LOSS` |
| 3 | Full | Daily `close < SMA50` | `EXIT_REASON_SMA_BREAKDOWN` |
| 4 | Full | EMA21 crosses below SMA50 | `EXIT_REASON_EMA_CROSS` |

After a stretch-trim the remaining shares continue to be held under normal
full-exit management on subsequent bars.

A regime change to `TREND_PRESSURE` or `TREND_END` on QQQ does **not**
force exits. Per-stock exits run independently. (The per-stock
`close < SMA50` rule is the analogue of Webster's "first break of the
50-day = step out" applied per name.)

**Margin / leverage**: disallowed in v1. Per-leg sizing and
`MAX_POSITIONS_OPEN` are calibrated assuming 1.0× buying power.
Revisiting leverage (only ever "on" while regime is `TREND_UP`) is a
future extension.

---

## Configuration (target `config.py`)

### Regime
| Constant | Value |
|---|---|
| `REGIME_SYMBOL` | `"QQQ"` |
| `REGIME_EMA_PERIOD` | `21` |
| `REGIME_SMA_PERIOD` | `50` |
| `LOW_ABOVE_EMA_DAYS` | `10` |
| `EMA_ABOVE_SMA_DAYS` | `5` |
| `SMA_SLOPE_LOOKBACK` | `1` |
| `REQUIRE_SMA50_RISING` | `True` |
| `REQUIRE_ACTIVATION_UPDAY` | `True` |
| `ENABLE_TREND_PRESSURE` | `True` |

### Volatility
| Constant | Value |
|---|---|
| `ATR_PERIOD` | `14` |
| `WEBBY_RSI_ATR_PERIOD` | `50` |
| `WEBBY_RSI_STRETCH_LEVEL` | `3.0` |

### Universe
| Constant | Value |
|---|---|
| `UNIVERSE_TOP_N` | `200` |
| `UNIVERSE_REFRESH_DAYS` | `14` (every 2 weeks) |
| `MIN_PRICE` | `20.0` |
| `MIN_DOLLAR_VOLUME` | `50_000_000` |
| `DOLLAR_VOLUME_LOOKBACK` | `20` |

### Entry / pyramiding
| Constant | Value |
|---|---|
| `STOCK_EMA_PERIOD` | `21` |
| `STOCK_SMA_PERIOD` | `50` |
| `STOCK_SMA10_PERIOD` | `10` |
| `PYRAMID_MAX_ADDS` | `3` |
| `INITIAL_LEG_SIZE_PCT` | `0.25` |

### Risk / exits
| Constant | Value |
|---|---|
| `MAX_POSITIONS_OPEN` | `10` |
| `STOP_LOSS_PCT` | `0.07` |
| `MAX_ACCOUNT_DRAWDOWN_PCT` | `0.15` |
| `PARTIAL_EXIT_TRIM_FRACTION` | `0.50` |

### Scheduling
| Constant | Value |
|---|---|
| `DAILY_EVAL_TIME` | `"09:35"` |

### Removed (carried over from template)
- All options block: `TARGET_DELTA`, `DELTA_TOLERANCE`, `MIN_OPEN_INTEREST_MULTIPLIER`, `IV_*`, `TRADING_DAYS_PER_YEAR`.
- Event window block: `MIN_DAYS_TO_EVENT`, `MAX_DAYS_TO_EVENT`, `EXIT_REASON_EVENT_PROXIMITY`.
- `FIXED_CONTRACTS`, `ENTRY_ZONE_EMAS`, `ENTRY_ZONE_TOLERANCE_PCT`, `MAX_ATR_EXTENSION`.
- `UNIVERSE_CSV_PATH` (universe is dynamic).

### New exit-reason constants
`EXIT_REASON_SMA_BREAKDOWN`, `EXIT_REASON_EMA_CROSS`, `EXIT_REASON_DRAWDOWN`, `EXIT_REASON_STRETCH_TRIM`.

---

## Behavioral Contract (Gherkin)

The following scenarios are the source-of-truth behavioral spec. Tests
in `tests/unit/` must enforce them.

### Background

```gherkin
Given the algorithm runs on daily resolution
And QQQ is subscribed as the regime symbol
And the tradable universe is the top 200 US equities by 20-day average
    dollar volume, refreshed every 14 days, filtered to price >= $20 and
    20-day avg dollar volume >= $50M
And the following indicators are computed daily per symbol:
  | Indicator | Period |
  | EMA       | 21     |
  | SMA       | 50     |
And rolling state is tracked for QQQ:
  | days_low_above_ema21 |
  | days_ema21_above_sma50 |
  | sma50_rising |
  | is_blue_bar (close >= open) |
```

### Scenario: QQQ Power Trend activates (strict — all 4 rules)

```gherkin
Given QQQ has sufficient warmup history
And REQUIRE_SMA50_RISING is True
And REQUIRE_ACTIVATION_UPDAY is True

When QQQ's daily low has been above the 21 EMA for at least 10 consecutive days
And QQQ's 21 EMA has been above the 50 SMA for at least 5 consecutive days
And QQQ's 50 SMA today is greater than yesterday's 50 SMA
And today's QQQ close is greater than or equal to today's QQQ open  # blue bar

Then the regime state is "TREND_UP"
And entries_allowed() returns True
```

### Scenario: QQQ Power Trend activates (lite mode — Webster personal)

```gherkin
Given QQQ has sufficient warmup history
And REQUIRE_SMA50_RISING is False
And REQUIRE_ACTIVATION_UPDAY is False

When QQQ's daily low has been above the 21 EMA for at least 10 consecutive days
And QQQ's 21 EMA has been above the 50 SMA for at least 5 consecutive days
# 50 SMA slope and activation-bar color are not required

Then the regime state is "TREND_UP"
And entries_allowed() returns True
```

### Scenario: Strict activation rejected on a red activation bar

```gherkin
Given REQUIRE_ACTIVATION_UPDAY is True
And the day-count and SMA-slope conditions for activation are met

When today's QQQ close is less than today's QQQ open  # red bar

Then the regime state remains "NO_TREND"
And entries_allowed() returns False
```

### Scenario: Weak / sideways QQQ rejects entries

```gherkin
Given QQQ's 21 EMA is below or equal to the 50 SMA
Or QQQ's moving averages are converging without separation

Then the regime state is "NO_TREND"
And entries_allowed() returns False
And no new entries are placed
```

### Scenario: QQQ Power Trend goes under pressure

```gherkin
Given the regime state is "TREND_UP"
And ENABLE_TREND_PRESSURE is True

When QQQ closes below its 50 SMA
And QQQ's 21 EMA is still above its 50 SMA

Then the regime state transitions to "TREND_PRESSURE"
And entries_allowed() returns False
And open positions are NOT force-closed
```

### Scenario: QQQ Power Trend re-arms from pressure

```gherkin
Given the regime state is "TREND_PRESSURE"

When QQQ's close is back above its 21 EMA
And QQQ's 21 EMA is above its 50 SMA

Then the regime state transitions back to "TREND_UP"
And entries_allowed() returns True
```

### Scenario: QQQ Power Trend deactivates

```gherkin
Given the regime state is "TREND_UP" or "TREND_PRESSURE"

When QQQ's 21 EMA crosses below its 50 SMA

Then the regime state transitions to "TREND_END"
And entries_allowed() returns False
And open positions are NOT force-closed
And per-stock exit rules continue to manage existing positions
```

### Scenario: Per-stock initial entry

```gherkin
Given regime.entries_allowed() returns True
And the account drawdown gate is open
And the open position count is below MAX_POSITIONS_OPEN
And no position is open for symbol X

When today's close > today's EMA21 > today's SMA50 for X
And yesterday's low <= yesterday's EMA21 for X
And today's close >= today's open for X        # blue bar

Then place a long market order for X sized at INITIAL_LEG_SIZE_PCT of portfolio value
```

### Scenario: Pyramiding add-on entry

```gherkin
Given a long position is open for symbol X
And leg_count for X is less than PYRAMID_MAX_ADDS
And regime.entries_allowed() returns True

When a new pullback occurred after the last leg's date
    (prior_low <= prior_EMA21 after last_leg_date)
And today's close >= today's open               # blue bar

Then place an additional long market order for X sized equal to the prior leg
And update last_leg_date and leg_count
```

### Scenario: Pyramiding cap respected

```gherkin
Given a long position is open for symbol X with leg_count == PYRAMID_MAX_ADDS

When an add-on signal would otherwise fire

Then no order is placed
```

### Scenario: Per-stock exit

```gherkin
Given a long position is open for symbol X

When any of the following triggers in priority order:
  | Priority | Trigger |
  | 1 | account drawdown >= MAX_ACCOUNT_DRAWDOWN_PCT |
  | 2 | current_price <= avg_entry_price * (1 - STOP_LOSS_PCT) |
  | 3 | today's close < today's SMA50 for X |
  | 4 | today's EMA21 < today's SMA50 for X |

Then close the entire X position with the corresponding exit reason
```

### Scenario: Account drawdown gate

```gherkin
Given the account equity has fallen 15% or more from its high-water mark

When the daily evaluation runs

Then no new entries (including pyramid adds) are placed
And existing positions continue to be managed by per-stock exits
```

### Scenario: Universe refresh

```gherkin
Given the previous universe selection ran more than UNIVERSE_REFRESH_DAYS ago

When the daily evaluation runs

Then the coarse universe is re-ranked by 20-day avg dollar volume
And only symbols with price >= MIN_PRICE and 20d avg dollar volume >= MIN_DOLLAR_VOLUME are eligible
And the top UNIVERSE_TOP_N are selected
And QQQ is force-included regardless of ranking
And raw share volume is NOT consulted at any stage of selection
```

### Scenario: Webby RSI fields are computed

```gherkin
Given indicators have been computed for symbol X

When data_handler.get_indicators(X) is called

Then the result includes atr_14, atr_50, SMA10, atr_stretch_low, high_vs_ema21, high_vs_sma10
And atr_stretch_low equals (today.low - today.EMA21) / today.atr_50
And high_vs_ema21 equals (today.EMA21 - today.high) / today.atr_50
And high_vs_sma10 equals (today.high - today.SMA10) / today.atr_50
And atr_stretch_low is not used as an entry gate in v1
```

### Scenario: Stretch-trim partial exit

```gherkin
Given a long position is open for symbol X
And no full-exit condition fires this bar

When today's high_vs_sma10 >= WEBBY_RSI_STRETCH_LEVEL

Then sell PARTIAL_EXIT_TRIM_FRACTION (50%) of total shares at market
And the remaining shares continue to be held
And no full-exit rule is evaluated for X this bar
```

---

## Backtesting Plan

- **Range:** 2003-01-01 → present. Covers dot-com tail, 2008 GFC, 2015–16 vol, 2020 COVID, 2022 bear, 2023–24 recovery.
- **Resolution:** Daily.
- **Data normalization:** Adjusted (splits + dividends).
- **Validation:** Walk-forward in 5-year train / 1-year out-of-sample windows. Tune only `STOP_LOSS_PCT`, `INITIAL_LEG_SIZE_PCT`, `PYRAMID_MAX_ADDS`, `MAX_POSITIONS_OPEN` — keep the four-rule regime thresholds (10/5/rising/blue-bar) frozen at Webster's published values.
- **Lite-mode comparison runs:** Run the full walk-forward five times to compare the strict default against Webster's personal relaxations:
  1. Strict default (all three toggles `True`).
  2. `REQUIRE_SMA50_RISING = False` only.
  3. `REQUIRE_ACTIVATION_UPDAY = False` only.
  4. `ENABLE_TREND_PRESSURE = False` only.
  5. Full lite (all three `False`).

  Compare CAGR, max drawdown, and trade count across the five runs. The strict default is the ship configuration unless lite shows a material out-of-sample edge.

### Performance targets (aspirational, not hard gates)

| Metric | Target |
|---|---|
| Max drawdown | ≤ 15% |
| Win rate | ≥ 60% |
| Risk / reward | ≥ 1.5 |
| Sharpe ratio | ≥ 1.2 |

---

## Phased Build Plan

| Phase | Scope |
|---|---|
| **0 (this doc)** | Strategy outline + Gherkin contract. No code. |
| ✅ 1 | Update `config.py`; rewrite `universe_filter.py` as `DynamicUniverseSelector` with 14-day refresh + QQQ force-include. |
| ✅ 2 | Implement `data_handler.py._compute_indicators` (EMA21, SMA50, prior values, 20d $-vol). |
| ✅ 3 | Implement `regime_filter.py` (rolling counters, state machine, `entries_allowed()`). |
| ✅ 4 | Implement `entry_engine.py` + `pyramiding_manager.py`; extend `position_manager.py` with multi-leg tracking. |
| ✅ 5 | Implement `exit_engine.py` + `risk_manager.py` (account DD gate). |
| ✅ 6 | Rewrite `main.py` (single daily `_evaluate()` callback; no two-phase split; no options). |
| 7 | 20-year backtest + walk-forward writeup. |

---

## Out of Scope (Future Extensions)

- **IBD-style distribution-day overlay** — a true distribution day per the
  source material is not just "down on volume"; it must consider:
  bar spread, close vs. open, close position within the bar's range,
  prior-day context, position relative to moving averages, and dollar
  volume rather than raw share volume. Any future overlay should model
  these dimensions, not the simplified IBD definition.
- **Sector concentration cap** (mega-cap tech bias of $-vol ranking).
- **Per-stock Power Trend classification** (currently QQQ-only — matches
  source material verbatim).
- **Death-cross / golden-cross awareness** as a logged context flag
  (chop expected near crossover); explicitly *not* a trading signal.
- **Margin / leverage gating** (only enabled while regime is `TREND_UP`).
- **Walk-forward harness automation** (manual recipe only for v1).
- **Live / paper deployment wiring**.
- **ATR-stretch entry gate** — promote `atr_stretch_low` from a logged diagnostic to a hard threshold (e.g. require `-1.0 ≤ atr_stretch_low ≤ 0.0` so entries fire only on shallow-but-real EMA21 pullbacks).
- **ATR-based stop loss** — replace the fixed `STOP_LOSS_PCT` with an ATR-multiple stop (e.g. `entry_price - k * atr_14`) so per-stock risk is volatility-normalized.
- **ATR-stretch leg sizing** — scale pyramid leg size inversely with `atr_stretch_low` so deeper pullbacks (more negative stretch) get larger adds and shallow ones get smaller adds.

---

## Implementation Notes

- This is **stateful logic**, not purely indicator-triggered. Rolling counters must be incremented incrementally — never recomputed by re-scanning history each bar.
- The QQQ regime filter is the **single shared gate** across the universe. Cache its state once per `_evaluate()` and read from all entry checks.
- Avoid entering during MA compression: the `sma50_rising` requirement is what enforces this.
- Pyramid adds require a **new** pullback after the previous leg — track `last_leg_date` on the trade record to enforce this and prevent rapid-fire stacking.
- All strategy thresholds belong in `config.py` as `Final`-typed constants. Never hardcode in handlers.
