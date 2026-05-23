---
name: entry-rules
description: |
  Per-stock initial entry and pyramid add-on trigger rules for the Power Trend Algo.
  Trigger phrases: "entry rules", "entry trigger", "pyramid add", "when to enter",
  "initial entry", "add-on entry", "pullback trigger", "entry conditions", "why no entries"
argument-hint: "Describe the entry scenario or paste indicator values (close, EMA21, SMA50, prior_close, prior_EMA21)"
---

# Entry Rules — Power Trend Algo

## Philosophy

Entries use a pullback-continuation trigger: the stock must be in a bullish trend (price stack)
and have recently pulled back to the EMA21, then reclaimed it with a higher close. This avoids
chasing breakouts and enters on low-risk pullback points within established trends.

**Hard boundaries:**
- No entries unless `RegimeFilter.entries_allowed()` returns `True`
- No entries if `MAX_POSITIONS_OPEN` (10) is already reached
- No add-on entries if the position already has `PYRAMID_MAX_ADDS` (3) legs
- Entries are evaluated once per day at `DAILY_EVAL_TIME` (09:35 ET)

---

## Initial Entry Conditions (all 5 must be True)

| # | Condition | Values Used | Config Constant |
|---|---|---|---|
| 1 | Price above EMA21 | `close > EMA21` | — |
| 2 | EMA21 above SMA50 | `EMA21 > SMA50` | — |
| 3 | Pullback: prior close at or below EMA21 | `prior_close <= prior_EMA21` | — |
| 4 | Higher close today | `close > prior_close` | — |
| 5 | Regime gate open | `regime.entries_allowed() == True` | `REGIME_SYMBOL` |

**All 5 conditions must be True simultaneously.** If any one fails, no entry is placed for
this symbol on this day.

---

## Pyramid Add-On Conditions

Same 5 conditions as initial entry, plus two additional guards:

| # | Additional Condition | Config Constant |
|---|---|---|
| 6 | Existing position in this symbol (leg_count ≥ 1) | — |
| 7 | Position not yet at max legs | `PYRAMID_MAX_ADDS` (3 adds, so max leg_count = 4) |

Add-on entries use the same `INITIAL_LEG_SIZE_PCT` (25%) per leg — equal-size adds only.

---

## Handler Contract

**File:** `handlers/entry_engine.py` | **Class:** `EntryEngine`

```python
class EntryEngine:
    def __init__(self, algorithm, regime, pyramiding_manager, position_manager) -> None: ...

    def evaluate(self, symbol: str, data: dict) -> bool:
        """
        Returns True and places an order if all entry conditions are met.
        data keys required: close, EMA21, SMA50, prior_close, prior_EMA21
        """
        ...
```

`data` is the dict from `DataHandler.get_indicators(symbol, today)`.

---

## Test Invariants

- All 5 conditions True → `evaluate()` returns `True`, order placed
- Condition 4 False (lower close today) → `evaluate()` returns `False`, no order
- Regime gate closed → `evaluate()` returns `False` even if conditions 1–4 are True
- Position count at `MAX_POSITIONS_OPEN` → `evaluate()` returns `False`
- Leg count at `PYRAMID_MAX_ADDS + 1` → add-on returns `False`
- No existing position → add-on conditions are not evaluated (falls through to initial entry)

---

## Handoff Menu

| Next Step | Trigger | Skill |
|---|---|---|
| Check regime gate rules | "regime gate", "entries allowed" | `trading/regime-filter-rules` |
| Check exit logic | "exit rules", "when to exit" | `trading/exit-rules` |
| Check pyramid leg sizing | "position sizing", "leg size" | `trading/pyramiding-rules` |
| Write entry engine tests | "write tests" | `lifecycle-workflows/write-unit-tests` |
| Implement the entry engine | "build entry engine" | `lifecycle-workflows/implement-handler` |

---

## Reference Files

- [Config thresholds](_shared/references/config-thresholds.md)
- [Full strategy spec](docs/STRATEGY_OVERVIEW.md)
