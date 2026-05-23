---
name: exit-rules
description: |
  Priority-ordered per-stock exit rules for the Power Trend Algo.
  Trigger phrases: "exit rules", "exit logic", "when to exit", "SMA breakdown",
  "stop loss", "exit conditions", "position exit", "EMA cross exit", "wrong exits",
  "exiting too early", "exiting too late"
argument-hint: "Describe the exit scenario or paste indicator values (close, EMA21, SMA50, prior_close) and position state (avg_cost)"
---

# Exit Rules — Power Trend Algo

## Philosophy

Exits are evaluated daily in strict priority order. A higher-priority exit pre-empts all lower
ones. This prevents conflicting exit signals and ensures the most severe risk condition always
wins. Holding period is open-ended — there is no time-based exit.

**Hard boundaries:**
- Priority order is non-negotiable — evaluate in the exact sequence below
- A position is always fully liquidated — no partial exits except via normal pyramid tracking
- Stop loss is calculated from per-position average cost (across all legs)
- Priority 1 (account drawdown) liquidates ALL positions, not just the current symbol

---

## Exit Priority Order

Evaluate in this exact order for each open position:

| Priority | Exit Type | Trigger | Config Constant |
|---|---|---|---|
| 1 (highest) | **Account drawdown gate** | `RiskManager.entries_suspended == True` → liquidate all positions | `MAX_ACCOUNT_DRAWDOWN_PCT` (15%) |
| 2 | **Stop loss** | `close < avg_cost × (1 - STOP_LOSS_PCT)` | `STOP_LOSS_PCT` (7%) |
| 3 | **SMA50 breakdown** | `close < SMA50` | — |
| 4 | **EMA21 cross** | `EMA21 < SMA50` (bullish stack broken) | — |
| 5 (lowest) | **Weakness** | `close < prior_close` AND `close < EMA21` | — |

- If Priority 1 fires → liquidate **all open positions** immediately
- If Priority 2–5 fires → exit **this symbol only**
- If no priority fires → hold; re-evaluate next day

---

## Handler Contract

**File:** `handlers/exit_engine.py` | **Class:** `ExitEngine`

```python
class ExitEngine:
    def __init__(self, algorithm, risk_manager, position_manager) -> None: ...

    def evaluate(self, symbol: str, data: dict, position: dict) -> str | None:
        """
        Returns exit reason if triggered, else None.
        Caller places the liquidation order.
        data keys: close, EMA21, SMA50, prior_close
        position keys: avg_cost, leg_count
        """
        ...
```

Return values: `"ACCOUNT_DD"`, `"STOP_LOSS"`, `"SMA_BREAKDOWN"`, `"EMA_CROSS"`, `"WEAKNESS"`, `None`

---

## Test Invariants

- Account drawdown gate active → returns `"ACCOUNT_DD"` for any symbol regardless of price
- `close < avg_cost × 0.93` → returns `"STOP_LOSS"` even if close is also below SMA50
- `close < SMA50` but stop loss not triggered → returns `"SMA_BREAKDOWN"`
- `EMA21 < SMA50` but close above SMA50 → returns `"EMA_CROSS"`, not `"SMA_BREAKDOWN"`
- All exit conditions False → returns `None`
- Priority order is respected: a stop loss overrides an SMA breakdown trigger

---

## Handoff Menu

| Next Step | Trigger | Skill |
|---|---|---|
| Check account drawdown gate logic | "drawdown gate", "account DD" | `trading/risk-rules` |
| Check entry conditions | "entry rules" | `trading/entry-rules` |
| Write exit engine tests | "write tests" | `lifecycle-workflows/write-unit-tests` |
| Implement the exit engine | "build exit engine" | `lifecycle-workflows/implement-handler` |

---

## Reference Files

- [Config thresholds](_shared/references/config-thresholds.md)
- [Full strategy spec](docs/STRATEGY_OVERVIEW.md)
