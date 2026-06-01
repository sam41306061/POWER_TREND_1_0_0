---
name: pyramiding-rules
description: |
  Equal-size pyramid leg sizing rules for the Power Trend Algo.
  Trigger phrases: "pyramiding", "leg sizing", "add-on entry", "position sizing",
  "pyramid adds", "PYRAMID_MAX_ADDS", "leg count", "equal size", "how big is each leg"
argument-hint: "Current position leg count and portfolio value, or describe the sizing scenario"
---

# Pyramiding Rules — Power Trend Algo

## Philosophy

Pyramid adds use equal-size legs. Each leg (initial entry or add-on) is sized at
`INITIAL_LEG_SIZE_PCT` (2%) of current portfolio value. This creates a balanced position
build-up that does not over-commit capital at entry and rewards continuation.
Max theoretical deployment = `MAX_POSITIONS_OPEN × (1 + PYRAMID_MAX_ADDS) × INITIAL_LEG_SIZE_PCT`
= 10 × 4 × 2% = 80%, leaving a ~20% cash buffer.

**Hard boundaries:**
- All legs must be equal size — no scaling into positions with larger or smaller adds
- Cap is `PYRAMID_MAX_ADDS` (3 adds) — the initial entry is leg 1, not counted as an add
- Sizing is always based on **current portfolio value**, not cost basis or entry price
- No add-ons if regime gate is closed (`entries_allowed() == False`)
- No add-ons if the position is already at max legs (leg_count == `PYRAMID_MAX_ADDS + 1`)

---

## Sizing Formula

```
order_value = current_portfolio_value × INITIAL_LEG_SIZE_PCT   # 2%
shares      = floor(order_value / current_close_price)
```

Apply identically for both initial entries and each add-on.

---

## Leg State Machine

```
Initial Entry → leg_count = 1
Add-on 1      → leg_count = 2   (requires entry conditions + can_add())
Add-on 2      → leg_count = 3   (requires entry conditions + can_add())
Add-on 3      → leg_count = 4   (requires entry conditions + can_add())  ← MAX
Any full exit → leg_count = 0   (remove_position() called by ExitEngine)
```

`PYRAMID_MAX_ADDS = 3` — maximum total legs = 4 (1 initial + 3 adds).

---

## Handler Contract

**File:** `handlers/pyramiding_manager.py` | **Class:** `PyramidingManager`

```python
class PyramidingManager:
    def __init__(self, algorithm) -> None: ...

    def can_add_more(self, leg_count: int) -> bool:
        """Returns True if leg_count < (1 + PYRAMID_MAX_ADDS)."""
        ...

    def size_leg(self, price: float, portfolio_value: float) -> int:
        """Returns number of shares for one leg: floor(INITIAL_LEG_SIZE_PCT * portfolio_value / price)."""
        ...
```

**Note:** Leg-count tracking (`add_leg`, `remove_position`) is owned by `PositionManager`,
not `PyramidingManager`. Call `PositionManager.add_leg()` after a fill is confirmed.
`PyramidingManager` is a pure sizing/cap utility with no internal state.

---

## Test Invariants

- `can_add_more(3)` returns `True`; `can_add_more(4)` returns `False`
- `size_leg()` uses `floor(INITIAL_LEG_SIZE_PCT * portfolio_value / price)`
- `size_leg()` returns an integer (floor division, never fractional shares)
- `size_leg()` returns 0 if price <= 0 or portfolio_value <= 0
- Leg-count state is tracked by `PositionManager.add_leg()`, not by `PyramidingManager`

---

## Common Failure Modes

| Symptom | Cause | Fix |
|---|---|---|
| Add-ons never fire even though indicators look right | `pyramiding_manager.can_add_leg(trade, ind)` reads `trade.leg_count` but trade is fetched via stale Symbol key, returning `None` → silently skipped | Re-key `PositionManager._trades` on canonical ticker. See `architecture-rules.md` "Symbol Identity" |
| Margin calls / "Insufficient buying power" warnings | `MAX_POSITIONS_OPEN × (1+PYRAMID_MAX_ADDS) × INITIAL_LEG_SIZE_PCT > 1.0` | `validate_config()` aggregate-exposure assertion enforces this; never weaken the assertion to silence it |
| All adds at one price (no pyramiding effect) | Add-on date guard relies on `trade.legs[-1].entry_date`; if symbol identity is broken, the same "first leg" is rewritten daily | Same as Symbol Identity row |

---

## Handoff Menu

| Next Step | Trigger | Skill |
|---|---|---|
| Check entry trigger conditions | "entry conditions" | `trading/entry-rules` |
| Check account-level risk gate | "drawdown gate", "risk rules" | `trading/risk-rules` |
| Write pyramiding manager tests | "write tests" | `lifecycle-workflows/write-unit-tests` |
| Implement the pyramiding manager | "build pyramiding manager" | `lifecycle-workflows/implement-handler` |

---

## Reference Files

- [Config thresholds](_shared/references/config-thresholds.md)
- [Handler responsibilities](_shared/references/handler-responsibilities.md)
