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

## Initial Entry Conditions (all 6 must be True)

| # | Condition | Values Used | Config Constant |
|---|---|---|---|
| 1 | Regime gate open | `regime.entries_allowed() == True` | `REGIME_SYMBOL` |
| 2 | Risk gate open | `risk.is_new_entry_allowed() == True` | `MAX_ACCOUNT_DRAWDOWN_PCT` |
| 3 | Blue bar today | `close >= open` (`is_blue_bar`) | — |
| 4 | Price above EMA21, EMA21 above SMA50 | `close > EMA21 > SMA50` | — |
| 5 | Pullback: prior low at or below prior EMA21 | `prior_low <= prior_EMA21` | — |
| 6 | Position limit not reached | `positions.can_add_position() == True` | `MAX_POSITIONS_OPEN` |

**All 6 conditions must be True simultaneously.** If any one fails, no entry is placed for
this symbol on this day.

---

## Pyramid Add-On Conditions

Same 6 conditions as initial entry, except condition 6 is replaced by two add-on guards:

| # | Additional Condition | Config Constant |
|---|---|---|
| 6a | Existing position in this symbol (leg_count ≥ 1) | — |
| 6b | Position not yet at max legs | `PYRAMID_MAX_ADDS` (3 adds, so max leg_count = 4) |
| 6c | New pullback is on a different day than the last leg fill date | `last_leg_date` on `TradeRecord` |

Add-on entries use the same `INITIAL_LEG_SIZE_PCT` (2%) per leg — equal-size adds only.

---

## Handler Contract

**File:** `handlers/entry_engine.py` | **Class:** `EntryEngine`

```python
class EntryEngine:
    def __init__(self, algorithm, regime, risk, position_manager, pyramiding) -> None: ...

    def evaluate(self, symbol: str, indicators: dict) -> str | None:
        """
        Returns EntrySignal.INITIAL, EntrySignal.ADD, or None.
        indicators keys required: close, open, EMA21, SMA50, prior_low, prior_EMA21, is_blue_bar
        """
        ...
```

`indicators` is the dict from `DataHandler.get_indicators(symbol, today)`.

---

## Test Invariants

- All 6 conditions True → `evaluate()` returns `EntrySignal.INITIAL`
- `is_blue_bar` False → `evaluate()` returns `None`, no order
- `prior_low > prior_EMA21` (no pullback) → `evaluate()` returns `None`
- Regime gate closed → `evaluate()` returns `None` even if conditions 3–6 are True
- Risk gate closed (drawdown ≥ 15%) → `evaluate()` returns `None`
- Position count at `MAX_POSITIONS_OPEN` → `evaluate()` returns `None`
- Leg count at `PYRAMID_MAX_ADDS + 1` (4) → add-on returns `None`
- Existing position, all conditions met, leg < 4 → returns `EntrySignal.ADD`
- Add-on attempted on same day as last leg fill → returns `None` (date guard)

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
- [Full strategy spec](../../../../STRATEGY_OVERVIEW.md)
