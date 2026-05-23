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
`INITIAL_LEG_SIZE_PCT` (25%) of current portfolio value. This creates a balanced position
build-up that does not over-commit capital at entry and rewards continuation.

**Hard boundaries:**
- All legs must be equal size — no scaling into positions with larger or smaller adds
- Cap is `PYRAMID_MAX_ADDS` (3 adds) — the initial entry is leg 1, not counted as an add
- Sizing is always based on **current portfolio value**, not cost basis or entry price
- No add-ons if regime gate is closed (`entries_allowed() == False`)
- No add-ons if the position is already at max legs (leg_count == `PYRAMID_MAX_ADDS + 1`)

---

## Sizing Formula

```
order_value = current_portfolio_value × INITIAL_LEG_SIZE_PCT   # 25%
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

    def can_add(self, symbol: str) -> bool:
        """Returns True if symbol's leg_count < (PYRAMID_MAX_ADDS + 1)."""
        ...

    def calculate_order_shares(self, symbol: str, close: float) -> int:
        """Returns number of shares for one leg at current portfolio value."""
        ...

    def record_leg(self, symbol: str) -> None:
        """Increments leg count by 1 after an order fills."""
        ...

    def remove_position(self, symbol: str) -> None:
        """Resets leg count to 0 on full exit."""
        ...
```

---

## Test Invariants

- `can_add()` returns `True` at `leg_count = 3`, `False` at `leg_count = 4`
- `calculate_order_shares()` uses `current_portfolio_value × INITIAL_LEG_SIZE_PCT / close`
- `calculate_order_shares()` returns an integer (floor division)
- `record_leg()` increments leg count by exactly 1
- `remove_position()` resets leg count to 0; subsequent `can_add()` returns `True`

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
