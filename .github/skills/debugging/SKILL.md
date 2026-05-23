---
name: debugging
description: |
  Diagnose why a Power Trend algorithm is not trading, or identify silent failure modes.
  Trigger phrases: "why isn't my algo trading", "diagnose no orders", "algo not placing orders",
  "silent failure", "debug algo", "no trades", "why no entries", "not trading"
argument-hint: "Paste the LEAN debug log output, or describe the symptom (no entries / wrong exits / stale indicators)"
---

# Debugging — Power Trend Algo

## Philosophy

Silent failures are the most dangerous bugs in algorithmic trading: the algo runs without errors
but produces no (or wrong) trades. This skill provides a systematic, phase-gated diagnostic
workflow specific to the Power Trend handler stack. Work phases in order — a failure at an
earlier phase makes later phases irrelevant.

**Hard boundaries:**
- Do not modify handler logic as part of diagnosis — only read and log
- Always confirm the regime gate state before investigating per-stock entry logic
- Config constants (thresholds) are never wrong — verify values against `config.py` first before
  concluding a threshold is misconfigured

---

## Phase 1 — Confirm Regime Gate

**Goal:** Verify `RegimeFilter` is allowing entries (`entries_allowed() == True`).

Add a log statement at the start of each daily evaluation:

```python
self._algorithm.debug(
    f"Regime state: {self._regime.current_state}, "
    f"entries_allowed: {self._regime.entries_allowed()}"
)
```

- If `entries_allowed = False` → regime is blocking. Continue in this phase.
- If `entries_allowed = True` → regime is open. Skip to Phase 3.

**Common causes of `entries_allowed = False`:**
- QQQ `low > EMA21` counter has not reached `LOW_ABOVE_EMA_DAYS` (10 days)
- QQQ `EMA21 > SMA50` counter has not reached `EMA_ABOVE_SMA_DAYS` (5 days)
- SMA50 is flat or declining (rising condition not met)
- Not enough history bars for indicator warm-up — check `IsReady` on both indicators

---

## Phase 2 — Verify Regime Indicator Readiness

**Goal:** Confirm QQQ indicators are warmed up and returning valid values.

Log QQQ indicator values:

```python
qqq_data = self._data_handler.get_indicators(self._algorithm.symbol("QQQ"), today)
self._algorithm.debug(
    f"QQQ EMA21={qqq_data.get('EMA21')}, SMA50={qqq_data.get('SMA50')}, "
    f"low={qqq_data.get('low')}"
)
```

If any value is `None` or `0.0`:
- Check warm-up period (`set_warm_up`) covers at least 50 bars
- Check QQQ is force-included in `universe_filter.py`
- Check `DataHandler` cache is cleared at the start of each daily evaluation cycle

---

## Phase 3 — Per-Stock Entry Gate Diagnosis

**Goal:** Identify why no per-stock entry triggers are firing.

Verify each condition in `EntryEngine` for your top candidates:

- [ ] `close > EMA21` — log both values per symbol
- [ ] `EMA21 > SMA50` — confirm the bullish stack exists
- [ ] Pullback condition met — `prior_close <= prior_EMA21`
- [ ] Higher close — `close > prior_close`
- [ ] `MAX_POSITIONS_OPEN` (10) not exceeded — count via `PositionManager`
- [ ] No existing position at max legs — check `PyramidingManager.can_add(symbol)`

---

## Phase 4 — Risk Gate & Drawdown Check

**Goal:** Confirm `RiskManager` is not suspending entries due to account drawdown.

```python
self._algorithm.debug(
    f"Account DD: {self._risk.current_drawdown:.1%}, "
    f"entries_suspended: {self._risk.entries_suspended}"
)
```

If `entries_suspended = True`:
- Current equity has dropped ≥ `MAX_ACCOUNT_DRAWDOWN_PCT` (15%) below high-water mark
- No entries will fire until equity recovers above the HWM gate threshold

---

## Handoff Menu

| Next Step | Trigger | Skill |
|---|---|---|
| Investigate regime counter logic | "regime not activating" | `trading/regime-filter-rules` |
| Investigate entry trigger conditions | "entry not firing" | `trading/entry-rules` |
| Investigate exit logic misfires | "wrong exits", "exiting too early" | `trading/exit-rules` |
| Apply a code fix | "apply fix", "fix the issue" | `lifecycle-workflows/implement-handler` |
| Open a PR with the fix | "create PR" | `lifecycle-workflows/create-pr` |

---

## Reference Files

- [Phase 1/2 gate detail](reference/why_didnt_my_algo_trade.md) *(note: contains content from a prior options strategy — cross-check conditions against Power Trend config)*
- [Silent failure catalogue](reference/silent_failure_modes.md) *(note: cache and data patterns are reusable; options-specific sections do not apply)*
- [Config thresholds](_shared/references/config-thresholds.md)
- [Handler responsibilities](_shared/references/handler-responsibilities.md)
