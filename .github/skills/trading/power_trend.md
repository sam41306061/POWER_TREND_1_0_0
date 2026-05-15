# Power Trend

> Source: Mike Webster (IBD / Market School) — transcribed and encoded
> Spec: `docs/STRATEGY_OVERVIEW.md` — "Power Trend Definition" section
> Codebase: `handlers/regime_filter.py`, `config.py`

---

## What Is a Power Trend?

A Power Trend identifies periods where a broad market index (QQQ in this
strategy) is in a **confirmed, sustained uptrend** — specifically one where:

1. Price is consistently holding above its short-term moving average (EMA21).
2. The short-term MA is pulling away from the medium-term MA (SMA50).

During a Power Trend, per-stock entry criteria are intentionally relaxed:
"During a Power Trend you can buy a stock whose low gets back above its
21-day without waiting for a follow-through day." — Webster

QQQ is the regime gate only; it is **never** traded.

---

## Activation Rules

### Strict (IBD / 4-rule)

All four must be true on the **same bar** to flip from `NO_TREND` → `TREND_UP`:

| Rule | Condition | Config toggle |
|------|-----------|---------------|
| 1 | `days_low_above_ema21 >= LOW_ABOVE_EMA_DAYS (10)` — QQQ's low has stayed above EMA21 for 10+ consecutive sessions | always on |
| 2 | `days_ema21_above_sma50 >= EMA_ABOVE_SMA_DAYS (5)` — EMA21 has been above SMA50 for 5+ consecutive sessions | always on |
| 3 | `SMA50 today > SMA50 yesterday` — 50-day SMA is rising | `REQUIRE_SMA50_RISING` |
| 4 | `close >= open` on the activation bar (blue bar) | `REQUIRE_ACTIVATION_UPDAY` |

Webster: "The hardest one is for your low to be above your 21-day for 10
consecutive days."

### Webster's Personal (2-rule, "lite")

Webster personally uses only rules 1 and 2 — he goes back and forth on
whether the SMA50 uptrend and blue-bar requirements add value:

> "For my version it's just two things: low is above the 21-day for
> 10 days, and the 21 is above 50 days for 5 days."

Lite mode is activated by setting both `REQUIRE_SMA50_RISING = False`
and `REQUIRE_ACTIVATION_UPDAY = False` in `config.py`.

---

## State Machine

```
         ┌─────────────────────┐
         │       NO_TREND      │◄──────────────────────────────────┐
         └────────┬────────────┘                                    │
                  │ all 4 activation rules fire                     │
                  ▼                                                  │
         ┌────────────────────┐   EMA21 < SMA50                    │
         │      TREND_UP      ├───────────────────────────────►TREND_END
         └──┬─────────────────┘                                     │ (one bar)
            │                 ▲                                      │
   close<SMA50 AND            │ close>EMA21 AND                     │
   EMA21>SMA50                │ EMA21>SMA50                         │
   (if ENABLE_TREND_PRESSURE) │                                     │
            ▼                 │                                      │
         ┌────────────────────┤   EMA21 < SMA50                    │
         │  TREND_PRESSURE    ├───────────────────────────────►TREND_END
         └────────────────────┘                                     │
                                                                     └──► NO_TREND
```

| State | `entries_allowed()` | New entries | Existing positions |
|-------|---------------------|-------------|-------------------|
| `NO_TREND` | `False` | Blocked | Managed by per-stock exits |
| `TREND_UP` | `True` | Allowed | Managed by per-stock exits |
| `TREND_PRESSURE` | `False` | Blocked | NOT force-closed |
| `TREND_END` | `False` | Blocked | NOT force-closed; resets to NO_TREND next bar |

---

## Warning Signs (Pre-Deactivation)

The official deactivation (`EMA21 < SMA50`) often lags the first visible
warning. Webster identifies early exits from strength as:

1. **Decisive break of the 21-day EMA** — close below EMA21, especially on
   high ATR extension downward (deeply negative `atr_stretch_low`).
2. **High stuck below EMA21** — multiple bars where `high_vs_ema21 > 0`
   (the bar's high can't reach the moving average from below).
3. **Break of the 50-day SMA** — `close < SMA50` while EMA21 > SMA50
   → triggers `TREND_PRESSURE` state in the codebase.

These are signals to reduce exposure and stop adding, not to force-exit.

---

## Re-Activation After Pressure / End

No cooldown period. If activation rules re-fire on the same bar that
`TREND_END` resets to `NO_TREND`, the regime immediately returns to
`TREND_UP`.

Webster's re-entry checklist (sequential, not all at once):
1. Close above EMA21.
2. Low above EMA21.
3. Low above EMA21 for **3 consecutive days** (the "Goldilocks" signal).
4. Resume treating conditions 1–2 as meaningful only after condition 3.

---

## Webby RSI During a Power Trend

Early in a new Power Trend, Webster looks for "power" — `atr_stretch_low`
values in the 2–3 ATR range — as confirmation the trend has momentum:

> "On the front end of the power trend, I want to make progress from the
> day I start measuring it. We saw a lot of examples where those ended up
> failing without ever making progress."

A power trend that never produces a meaningful wall of blue (> 1 ATR
for many consecutive bars) is more likely to fail or reverse quickly.
See [webby_rsi.md](webby_rsi.md) for the indicator definition.

---

## Codebase Reference

| Symbol | Location |
|--------|---------|
| `RegimeFilter` | `handlers/regime_filter.py` |
| `LOW_ABOVE_EMA_DAYS`, `EMA_ABOVE_SMA_DAYS` | `config.py` |
| `REQUIRE_SMA50_RISING`, `REQUIRE_ACTIVATION_UPDAY`, `ENABLE_TREND_PRESSURE` | `config.py` |
| `REGIME_NO_TREND`, `REGIME_TREND_UP`, `REGIME_TREND_PRESSURE`, `REGIME_TREND_END` | `config.py` |
