---
name: risk-rules
description: |
  Account-level risk management rules for the Power Trend Algo. High-water mark tracking
  and account drawdown gate.
  Trigger phrases: "risk management", "drawdown gate", "account drawdown", "HWM",
  "high water mark", "entries suspended", "MAX_ACCOUNT_DRAWDOWN_PCT", "risk rules",
  "account level risk"
argument-hint: "Current equity and high-water mark values, or describe the risk behavior you want to understand"
---

# Risk Rules — Power Trend Algo

## Philosophy

Account-level risk is managed by a high-water mark (HWM) drawdown gate. When portfolio
drawdown exceeds `MAX_ACCOUNT_DRAWDOWN_PCT` from its peak, all new entries are suspended
**and all existing positions are liquidated**. This is a full defensive stop — not a soft brake.

**Hard boundaries:**
- HWM only moves up — never decreases
- A drawdown breach triggers immediate liquidation of ALL positions (handled by `ExitEngine` Priority 1)
- Gate does not auto-reset — entries remain suspended until equity recovers above the HWM threshold
- Drawdown is measured at portfolio level, not per-position

---

## High-Water Mark Logic

```python
HWM = max(HWM, current_portfolio_value)   # updated daily at DAILY_EVAL_TIME
drawdown = (HWM - current_portfolio_value) / HWM
entries_suspended = drawdown >= MAX_ACCOUNT_DRAWDOWN_PCT   # 0.15
```

`MAX_ACCOUNT_DRAWDOWN_PCT = 0.15` (15%)

---

## Suspension Behavior

| State | `is_new_entry_allowed()` | Effect |
|---|---|---|
| Drawdown < 15% | `True` | Normal operation — entries evaluated per day |
| Drawdown ≥ 15% | `False` | `EntryEngine.evaluate()` returns `None`; `ExitEngine.check()` Priority 1 fires → liquidate all |
| Equity recovers above HWM gate | `True` again | Entries resume automatically next evaluation |

**Note:** HWM is not reset when entries resume. The same HWM peak is maintained across the
full backtest/live session.

---

## Handler Contract

**File:** `handlers/risk_manager.py` | **Class:** `RiskManager`

```python
class RiskManager:
    def __init__(self, algorithm) -> None: ...

    def update(self, equity: float) -> None:
        """Called daily. Updates HWM and recomputes drawdown."""
        ...

    def is_new_entry_allowed(self) -> bool:
        """Returns True when current drawdown < MAX_ACCOUNT_DRAWDOWN_PCT (i.e., entries are open)."""
        ...

    @property
    def drawdown(self) -> float:
        """Current drawdown as a fraction (e.g., 0.12 for 12%)."""
        ...
```

---

## Test Invariants

- Portfolio value rises → HWM updates to new peak
- Portfolio value falls → HWM holds at the prior peak (monotonically non-decreasing)
- `drawdown >= 0.15` → `is_new_entry_allowed() == False`
- `drawdown < 0.15` → `is_new_entry_allowed() == True`
- HWM never decreases between two consecutive `update()` calls
- `hwm == 0` → `drawdown` returns `0.0` (no division by zero)

---

## Common Failure Modes

| Symptom | Cause | Fix |
|---|---|---|
| HWM resets each session | `update()` reads portfolio value before warm-up; HWM persisted as 0 | Skip HWM updates while `algorithm.is_warming_up` is True |
| Drawdown gate never closes despite -20% equity curve | Gate read from cached value never refreshed; or called only inside an entry path that's already filtered out | Call `risk.update(portfolio_value)` first in every daily evaluation, before any gates |
| 15% drawdown threshold tripped on intraday noise | Using mark-to-market intra-bar instead of EOD portfolio value | Reset HWM/DD using EOD `algo.portfolio.total_portfolio_value` only |

---

## Handoff Menu

| Next Step | Trigger | Skill |
|---|---|---|
| Check exit logic that fires on account DD | "exit on drawdown", "Priority 1" | `trading/exit-rules` |
| Write risk manager tests | "write tests" | `lifecycle-workflows/write-unit-tests` |
| Implement the risk manager | "build risk manager" | `lifecycle-workflows/implement-handler` |

---

## Reference Files

- [Config thresholds](_shared/references/config-thresholds.md)
- [Full strategy spec](../../../../STRATEGY_OVERVIEW.md)
