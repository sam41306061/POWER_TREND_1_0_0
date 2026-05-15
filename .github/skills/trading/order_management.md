# Order Management

> Scope: entry sizing, exit priority waterfall, partial trims, and re-entry
> checklist for Power Trend Algo 1.
> Codebase: `handlers/exit_engine.py`, `handlers/pyramiding_manager.py`,
>            `handlers/position_manager.py`, `main.py`

---

## Exit Priority Waterfall

Exits are evaluated **once per day** at `DAILY_EVAL_TIME` (09:35 ET), in
strict priority order.  The first rule that fires wins; lower-priority
rules are not evaluated for the same position on the same bar.

### Priority 0 — Stretch Trim (Partial)

**Trigger:** `high_vs_sma10 >= WEBBY_RSI_STRETCH_LEVEL` (default 3.0 ATRs)

Sell `PARTIAL_EXIT_TRIM_FRACTION` (50 %) of total shares at market open.
The remaining half of the position continues to be held; full-exit rules
apply on subsequent bars as normal.

This trim is implemented as a **partial** sell, not a full close. The
`PositionManager.reduce_position()` method removes shares LIFO from the
most-recent leg so oldest cost-basis legs remain intact.

Webster: "When you're up near three… you still have your foot on the gas
but you want to be locking in some offensive gains and any new positions,
be very careful."

*Note: If a stretch trim fires on a given bar, the full-exit rules below
are skipped for that bar.*

### Priority 1 — Account Drawdown Gate

**Trigger:** Portfolio has fallen `MAX_ACCOUNT_DRAWDOWN_PCT` (15 %) or more
from its high-water mark.

Close the entire position immediately (`EXIT_REASON_DRAWDOWN`).
Also suspends new entries until equity recovers.

### Priority 2 — Stop Loss

**Trigger:** `close <= avg_entry_price * (1 - STOP_LOSS_PCT)` (7 % below
average fill price across all legs).

Close the entire position (`EXIT_REASON_STOP_LOSS`).

### Priority 3 — SMA50 Breakdown

**Trigger:** `close < SMA50` on a per-stock basis.

This is the per-stock analogue of Webster's "first break of the 50-day =
step out." Close the entire position (`EXIT_REASON_SMA_BREAKDOWN`).

*Regime note: A QQQ close below SMA50 triggers `TREND_PRESSURE`, not an
exit. Per-stock exits always run independently of the regime state.*

### Priority 4 — EMA21/SMA50 Cross

**Trigger:** `EMA21 < SMA50` for the individual stock.

The stock's own short-term momentum has crossed below medium-term trend.
Close the entire position (`EXIT_REASON_EMA_CROSS`).

---

## Re-Entry Checklist (After Power Trend End)

When `TREND_END` resets to `NO_TREND` (and then possibly re-activates),
Webster describes a sequential checklist before resuming aggressive buying:

| Step | Condition | Action |
|------|-----------|--------|
| 1 | `close > EMA21` | First watch signal — market is trying |
| 2 | `low > EMA21` | Confirmation — the day's low held above EMA21 |
| 3 | `low > EMA21` for **3 consecutive days** | Goldilocks signal — resume entries |

Only after step 3 is met should the algorithm (or trader) treat new
entry signals as high-confidence. Two days is "too soon," five days is
"too late" per Webster's analysis.

The `RegimeFilter` handles re-activation automatically: once all
activation rules re-fire, `entries_allowed()` returns `True` again.
The re-entry checklist above is the human/discretionary overlay that
the Webby RSI's wall-of-blue visually confirms.

---

## What Does NOT Force Exits

- QQQ regime transitioning to `TREND_PRESSURE` or `TREND_END`.
- Universe refresh (a symbol leaving the top-200 list).
- Regime returning to `NO_TREND`.

Per-stock exit rules (above) are the only exit mechanism. Regime changes
only gate **new entries**.

---

## Sizing Rules

### Initial Leg

```
shares = floor(INITIAL_LEG_SIZE_PCT * current_free_cash / close)
```

`current_free_cash` is re-read each iteration of the entry loop so each
successive order in the same evaluation cycle naturally shrinks the
available capital for the next.

### Pyramid Add

Same formula as the initial leg — equal-size legs throughout.
Maximum legs per position = `1 + PYRAMID_MAX_ADDS` (default 4 legs total).

### Sizing Gate

`MAX_POSITIONS_OPEN` (10) caps concurrent open positions.
After submitting any order that fills the slot, the entry loop checks
`can_add_position()` and breaks if the cap is reached.

---

## Codebase Reference

| Symbol | Location |
|--------|---------|
| `ExitEngine.check()` | `handlers/exit_engine.py` |
| `ExitEngine.check_partial()` | `handlers/exit_engine.py` |
| `PositionManager.reduce_position()` | `handlers/position_manager.py` |
| `PyramidingManager.size_leg()` | `handlers/pyramiding_manager.py` |
| `STOP_LOSS_PCT`, `MAX_ACCOUNT_DRAWDOWN_PCT` | `config.py` |
| `PARTIAL_EXIT_TRIM_FRACTION`, `WEBBY_RSI_STRETCH_LEVEL` | `config.py` |
| `EXIT_REASON_*` constants | `config.py` |
