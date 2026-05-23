---
name: regime-filter-rules
description: |
  Power Trend regime filter state machine rules for QQQ. Defines when entries are allowed.
  Trigger phrases: "regime filter", "power trend state", "entries allowed", "QQQ gate",
  "regime not activating", "TREND_UP", "regime counter", "when does regime activate",
  "entries allowed", "QQQ regime"
argument-hint: "Current QQQ indicator values (EMA21, SMA50, low) or describe the regime behavior you want to understand"
---

# Regime Filter Rules — Power Trend Algo

## Philosophy

The regime filter is the master gate for all new entries. It implements a Mike Webster–style
Power Trend classifier on QQQ only. When the regime is not in `TREND_UP`, no new positions
may be opened — regardless of per-stock signals.

**Hard boundaries:**
- Only QQQ feeds the regime filter — never per-stock data
- `entries_allowed()` is the only public gate — no handler may bypass it
- State machine resets counters on any breach — partial counter accumulation is lost

---

## State Machine

**States:** `NO_TREND` | `TREND_UP` | `TREND_PRESSURE` | `TREND_END`

### Activation → TREND_UP

All four conditions must be met **simultaneously** on QQQ:

| Condition | Threshold | Config Constant |
|---|---|---|
| QQQ `low > EMA21` for N consecutive days | 10 days | `LOW_ABOVE_EMA_DAYS` |
| QQQ `EMA21 > SMA50` for N consecutive days | 5 days | `EMA_ABOVE_SMA_DAYS` |
| QQQ SMA50 is rising (today > yesterday) | 1 day | `REQUIRE_SMA50_RISING` (toggle) |
| Blue bar: QQQ `close >= open` on activation day | 1 day | `REQUIRE_ACTIVATION_UPDAY` (toggle) |

Counters increment daily at `DAILY_EVAL_TIME` (09:35 ET). If any condition breaks, that
counter resets to 0. State remains `NO_TREND` until all counters simultaneously reach threshold.

### TREND_PRESSURE (sub-state of bullish regime)

Fires when `ENABLE_TREND_PRESSURE = True` and QQQ `close < SMA50` while `EMA21 > SMA50`.
Entries are **blocked** in `TREND_PRESSURE` (same as `NO_TREND`). The state recovers to
`TREND_UP` when `close > EMA21` and `EMA21 > SMA50` both return True.

### Deactivation

| Trigger | New State |
|---|---|
| `EMA21 < SMA50` (EMA crosses below SMA50) | `TREND_END` |

`TREND_END` is a one-bar label. On the next bar the state machine resets to `NO_TREND` and
counters must re-accumulate from scratch before a new `TREND_UP` can be declared.
On deactivation: all counters reset to 0. `entries_allowed()` returns `False`.

---

## Handler Contract

**File:** `handlers/regime_filter.py` | **Class:** `RegimeFilter`

```python
class RegimeFilter:
    def __init__(self, algorithm) -> None: ...

    def update(self, qqq_data: dict) -> str:
        """Called daily with QQQ indicator values. Updates counters and state.
        Returns the new current_state string."""
        ...

    def entries_allowed(self) -> bool:
        """Returns True only when current_state == 'TREND_UP'."""
        ...

    @property
    def current_state(self) -> str:
        """Returns 'NO_TREND', 'TREND_UP', 'TREND_PRESSURE', or 'TREND_END'."""
        ...
```

`qqq_data` is the dict from `DataHandler.get_indicators(REGIME_SYMBOL, today)`.
Required keys: `close`, `open`, `EMA21`, `SMA50`, `low`, `prior_SMA50`, `is_blue_bar`

---

## Test Invariants

- Counter reaches `LOW_ABOVE_EMA_DAYS` (10) on day 10 → state becomes `TREND_UP` *(if all other conditions met)*
- Counter resets to 0 if `low < EMA21` on day 9 → state stays `NO_TREND`
- `entries_allowed()` returns `False` when `current_state != 'TREND_UP'`
- SMA50 declining on activation day → state stays `NO_TREND` regardless of counters (when `REQUIRE_SMA50_RISING = True`)
- Blue bar not met on activation day → state stays `NO_TREND` (when `REQUIRE_ACTIVATION_UPDAY = True`)
- After `TREND_END` → state resets to `NO_TREND` next bar; counters are 0 and must re-accumulate
- `TREND_PRESSURE`: `close < SMA50` while `EMA21 > SMA50` → state becomes `TREND_PRESSURE`; `entries_allowed()` returns `False`
- Recovery from `TREND_PRESSURE`: `close > EMA21` and `EMA21 > SMA50` → state returns to `TREND_UP`

---

## Handoff Menu

| Next Step | Trigger | Skill |
|---|---|---|
| Implement the RegimeFilter handler | "build regime filter" | `lifecycle-workflows/implement-handler` |
| Write tests for regime filter | "write tests" | `lifecycle-workflows/write-unit-tests` |
| Understand entry trigger rules | "entry rules" | `trading/entry-rules` |
| Debug why regime isn't activating | "diagnose" | `debugging` |

---

## Reference Files

- [Config thresholds](_shared/references/config-thresholds.md)
- [Full strategy spec](docs/STRATEGY_OVERVIEW.md)
