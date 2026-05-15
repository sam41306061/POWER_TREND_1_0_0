# Webby RSI (Really Simple Indicator)

> Author: Mike Webster ("Webby")
> Pine Script reference: `Webby RSI 2.0` (© Amphibiantrading, MPL 2.0)
> Codebase fields: `atr_50`, `atr_stretch_low`, `high_vs_ema21`, `high_vs_sma10` in `data_handler.py`

---

## What It Is

A histogram indicator that quantifies **how far price is from its 21-day EMA**,
expressed in **50-period ATR units** rather than percentage points.

ATR normalisation makes the magnitude comparable across:
- Different instruments (slow-moving Costco vs high-velocity growth stocks).
- Different volatility regimes (calm 2017 vs volatile 2022).
- Leveraged ETFs vs their underlying index.

Webster deliberately uses only OHLC data — no volume, no options flow, no
secondary indicators — because "you know those four values for certain."

---

## The Three Components

### 1. `atr_stretch_low` (blue / bullish histogram)

```
atr_stretch_low = (low - EMA21) / ATR(50)
```

- **Positive** when the day's low is above the 21-day EMA (bullish zone).
- **Zero / negative** when the low breaches the EMA (reset).
- A sustained "wall of blue" (consistently positive values over many bars)
  is Webster's primary visual signal of a healthy trend worth trading
  aggressively.

In the codebase: `data_handler` computes this as `atr_stretch_low`.

### 2. `high_vs_ema21` (red / bearish histogram)

```
high_vs_ema21 = (EMA21 - high) / ATR(50)
```

- **Positive** when the day's *high* is below the 21-day EMA — the bar
  failed to even touch the moving average from below.
- A high positive reading means the market is living under the EMA (bearish pressure).
- Used as a regime warning: if bars are printing here, entries are likely wrong.

In the codebase: `data_handler` computes this as `high_vs_ema21`.

### 3. `high_vs_sma10` (orange line — stretch / partial-take signal)

```
high_vs_sma10 = (high - SMA10) / ATR(50)
```

- Measures how far the day's high extends above the **10-day simple MA**.
- Webster uses this to identify "running out of gas" moments where locking
  in partial gains makes sense.
- At **3 ATRs** this becomes an action level (see [Partial Exit rule](#partial-exit-rule)).

In the codebase: `data_handler` computes this as `high_vs_sma10`.

---

## Key Levels

| ATR level | Meaning |
|-----------|---------|
| 0 | Low exactly at EMA21 (neutral) |
| 0.5 – 3.0 | Sweet spot — trend is healthy, momentum is sustainable |
| ≥ 3.0 | Stretched — high probability of mean reversion; trim into strength |
| < 0 (low below EMA21) | Pullback / choppy — do not open new positions |

Webster: "When you're up near three — like 2.30 to 3.00 — you still have
your foot on the gas but you want to be locking in some offensive gains
and any new positions, be very careful."

---

## ATR Parameters

| ATR | Period | Purpose |
|-----|--------|---------|
| `atr_14` | 14 | Stop-loss sizing, `atr_stretch_low` (14-period legacy field) |
| `atr_50` | 50 | Webby RSI normalisation (`WEBBY_RSI_ATR_PERIOD`) |

The two ATR windows exist because the stop-loss calculation (per the
strategy spec) uses the shorter window, while Webby RSI requires the
longer window for smooth, regime-comparable readings.

---

## Version History

| Version | Change |
|---------|--------|
| 1.0 | `(low - EMA21) / price` as percentage — non-comparable across instruments |
| 2.0 / 5.150 | Switched to ATR normalisation; added `high_vs_ema21` and `high_vs_sma10` |

---

## Partial Exit Rule

When `high_vs_sma10 >= WEBBY_RSI_STRETCH_LEVEL` (default 3.0), the exit engine
calls `check_partial()` and the algorithm trims `PARTIAL_EXIT_TRIM_FRACTION`
(50 %) of the position at market open the next bar.

This partial trim fires **before** any full-exit check in the same bar.
After a trim the remaining position continues to be held; full-exit rules
apply normally on subsequent bars.

---

## Codebase Reference

| Symbol | Location |
|--------|---------|
| `WEBBY_RSI_ATR_PERIOD = 50` | `config.py` |
| `WEBBY_RSI_STRETCH_LEVEL = 3.0` | `config.py` |
| `PARTIAL_EXIT_TRIM_FRACTION = 0.50` | `config.py` |
| `STOCK_SMA10_PERIOD = 10` | `config.py` |
| `atr_50`, `high_vs_ema21`, `high_vs_sma10`, `SMA10` | `handlers/data_handler.py` |
| `check_partial()` | `handlers/exit_engine.py` |
| `reduce_position()` | `handlers/position_manager.py` |
