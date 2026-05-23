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
| 0 (pre-check) | **Stretch-trim partial** | `high_vs_sma10 >= WEBBY_RSI_STRETCH_LEVEL` (3.0 ATR) → sell `PARTIAL_EXIT_TRIM_FRACTION` (50%) | `WEBBY_RSI_STRETCH_LEVEL`, `PARTIAL_EXIT_TRIM_FRACTION` |
| 1 (highest) | **Account drawdown gate** | `risk.drawdown >= MAX_ACCOUNT_DRAWDOWN_PCT` (15%) → liquidate all positions | `MAX_ACCOUNT_DRAWDOWN_PCT` |
| 2 | **Stop loss** | `close <= avg_entry_price × (1 - STOP_LOSS_PCT)` | `STOP_LOSS_PCT` (7%) |
| 3 | **SMA50 breakdown** | `close < SMA50` | — |
| 4 (lowest) | **EMA21 cross** | `EMA21 < SMA50` (bullish stack broken) | — |

- P0 (stretch-trim) is a **partial** exit: sells 50% of shares via `reduce_position()`, does not close the trade
- If Priority 1 fires → liquidate **all open positions** immediately
- If Priority 2–4 fires → exit **this symbol only** (full liquidation)
- If no priority fires → hold; re-evaluate next day

---

## Handler Contract

**File:** `handlers/exit_engine.py` | **Class:** `ExitEngine`

```python
class ExitEngine:
    def __init__(self, algorithm, risk) -> None: ...

    def check_partial(self, trade, indicators: dict) -> tuple[bool, str | None]:
        """
        Returns (should_trim, reason) for the P0 stretch-trim partial exit.
        reason is EXIT_REASON_STRETCH_TRIM when should_trim is True, else None.
        """
        ...

    def check(self, trade, indicators: dict) -> tuple[bool, str | None]:
        """
        Returns (should_exit, reason) for full-exit priorities P1–P4.
        indicators may be None when symbol falls out of universe;
        P1 (drawdown) still evaluates; P2 (stop loss) uses trade.last_known_price as fallback.
        """
        ...
```

Return reason values: `EXIT_REASON_DRAWDOWN`, `EXIT_REASON_STOP_LOSS`,
`EXIT_REASON_SMA_BREAKDOWN`, `EXIT_REASON_EMA_CROSS`, `EXIT_REASON_STRETCH_TRIM`

---

## Test Invariants

- `check_partial()`: `high_vs_sma10 >= 3.0` → returns `(True, EXIT_REASON_STRETCH_TRIM)`
- `check_partial()`: `high_vs_sma10 < 3.0` → returns `(False, None)`
- `check()`: `risk.drawdown >= 0.15` → returns `(True, EXIT_REASON_DRAWDOWN)` for any symbol regardless of price
- `check()`: `close <= avg_entry_price × 0.93` → returns `(True, EXIT_REASON_STOP_LOSS)` even if close is also below SMA50
- `check()`: `close < SMA50` but stop loss not triggered → returns `(True, EXIT_REASON_SMA_BREAKDOWN)`
- `check()`: `EMA21 < SMA50` but close above SMA50 → returns `(True, EXIT_REASON_EMA_CROSS)`, not `SMA_BREAKDOWN`
- `check()`: all exit conditions False → returns `(False, None)`
- `check()`: `indicators=None` → P1 (drawdown) still fires; P2 uses `trade.last_known_price` fallback; P3/P4 cannot fire
- Priority order is respected: stop loss overrides SMA breakdown trigger

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
