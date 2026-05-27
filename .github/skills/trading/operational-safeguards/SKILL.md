---
name: operational-safeguards
description: |
  Production-only safeguards required for live trading the Power Trend algo on QuantConnect:
  state persistence via Object Store, restart reconciliation against broker holdings,
  expanded order-lifecycle handling (INVALID / CANCELED / PARTIALLY_FILLED), pending-order
  stale GC, a runtime kill switch, and operational alerting via self.notify.
  Trigger phrases: "operational safeguards", "state persistence", "object store",
  "restart reconciliation", "kill switch", "order lifecycle", "partial fills",
  "notify email", "notify webhook", "pending order GC"
argument-hint: "Name the safeguard to implement or audit (state / reconciliation / lifecycle / kill-switch / alerting)"
---

# Operational Safeguards — Power Trend Algo

## Philosophy

Backtests run cleanly because LEAN fills synchronously, never restarts, and has no
broker rejecting orders. Live mode does all three. QC's own docs are explicit:
*"There is no automatic state management of live strategies."* and *"In the event
the algorithm is terminated unexpectedly, you should review the live algorithm
portfolio at the brokerage to confirm it will behave as expected."*

These safeguards are **production-only code paths** — they must be no-ops in
backtest (gated by `self.live_mode`) so backtest equity curves remain unchanged.

**Hard boundaries:**
- All safeguards live in `handlers/` as pure Python; only `main.py` touches the
  LEAN platform APIs (`self.object_store`, `self.notify`, `self.portfolio`)
- No safeguard may modify strategy thresholds in `config.py` trading constants
- Backtest behavior must remain bit-identical after each safeguard is added
- Reconciliation never silently mutates the broker — it logs and either adopts
  or flattens per configured policy

---

## Safeguard 1 — State Persistence

**Problem:** `_pending_orders`, `PositionManager._trades`, and `RiskManager` HWM
all live in memory. Live nodes restart on deploy and on crashes; without
persistence, pyramid leg counts, average entry prices, and HWM are lost.

**Implementation:**
- New handler `handlers/state_store.py`, pure Python, constructor `__init__(self, algorithm)`
- Methods: `save(key: str, payload: dict)` and `load(key: str) -> dict | None`
  that route through `self._algorithm.object_store` (string keys, JSON values)
- Serialize on every fill in `on_order_event` AND once daily after `_evaluate()`
- Deserialize in `initialize()` after handlers are constructed, BEFORE warmup completes
- Keys: `power_trend/trades`, `power_trend/pending_orders`, `power_trend/risk_hwm`

**Trade serialization contract:** position_manager must expose
`to_dict() / from_dict(payload)` round-trip methods so the store stays
schema-agnostic.

**Backtest safety:** the store wraps reads/writes in `if self._algorithm.live_mode:`
— backtest runs never persist.

---

## Safeguard 2 — Restart Reconciliation

**Problem:** On live restart LEAN re-populates `self.portfolio` with broker holdings
and `self.transactions` with open orders, but `position_manager._trades` is whatever
the state store loaded (which may lag the broker if the algo crashed mid-fill).

**Implementation:**
- New `_reconcile_on_start()` in `main.py`, called once after warmup completes
  (use the `on_warmup_finished` callback)
- For each holding in `self.portfolio` with `invested == True`:
  - If symbol exists in `_trades`: log OK
  - If symbol NOT in `_trades`: log warning, action per `RECONCILE_ORPHAN_POLICY`
    config flag (default `"flatten"`; alt `"adopt_as_single_leg"`)
- For each open order in `self.transactions.get_open_orders()`:
  - If in `_pending_orders`: log OK
  - Else: cancel via `self.transactions.cancel_order(...)`, log
- Always send a notification with the reconciliation summary

---

## Safeguard 3 — Expanded Order Lifecycle

**Problem:** Current `on_order_event` only acts on `OrderStatus.FILLED`. QC docs:
*"Orders fill asynchronously in live trading"* — they can also become
`INVALID`, `CANCELED`, or `PARTIALLY_FILLED`. Pending entries for rejected orders
leak in `_pending_orders` forever and block the position cap.

**Required handling:**

| Status | Action |
|---|---|
| `FILLED` | Current behavior: route to position_manager |
| `PARTIALLY_FILLED` | Accumulate in a per-order `filled_qty` counter; only commit a `position_manager.add_leg(...)` when fully filled OR at end-of-day cleanup |
| `CANCELED` | Pop from `_pending_orders`, log, notify if it was an `"exit"` (failed risk action!) |
| `INVALID` | Pop from `_pending_orders`, log error, notify always |
| `SUBMITTED` / `NEW` / `UPDATE_SUBMITTED` | No action |

A partial-fill at session end that never completes is closed at next-day open
under stale-order GC (Safeguard 4).

---

## Safeguard 4 — Pending-Order Stale GC

**Problem:** Already partially fixed (we count pending entries against the cap),
but yesterday's never-filled pending entry will block today's slot forever if
not GC'd.

**Implementation:** at the top of `_evaluate()`, before any entry decisions,
remove any `_pending_orders` entry whose submission `algo_time` is more than
1 trading day old. For each GC'd entry, attempt `transactions.cancel_order(...)`
defensively, log, and notify.

`_pending_orders` meta must therefore include a `"submitted_at"` timestamp
(currently it only has `type`, `symbol`, `reason`).

---

## Safeguard 5 — Runtime Kill Switch

**Problem:** A live anomaly (data feed gap, brokerage outage, suspect signals)
must be pauseable without a redeploy.

**Implementation:**
- At top of `_evaluate()` (after exit checks, before entry checks):
  - `if self.object_store.contains_key("power_trend/kill_switch"): return`
  - Operator sets/removes this key from the QC research/console
- Existing positions continue to be managed by the exit block, so a kill switch
  prevents NEW entries only — never silently liquidates

Surface this in the algo's daily log so the dashboard reflects current state.

---

## Safeguard 6 — Operational Alerting

**Problem:** `self.log` is invisible until someone opens the live log. Critical
events need push notifications.

**Use the LEAN notification API** ([live-trading/notifications](https://www.quantconnect.com/docs/v2/writing-algorithms/live-trading/notifications)):
- `self.notify.email(address, subject, message)`
- `self.notify.web(url, data, headers)` for webhooks (Slack, Discord, custom)
- `self.notify.telegram(id, message, token)` (optional)

**Mandatory alert events:**

| Event | Channel | Source |
|---|---|---|
| Drawdown gate trips (entries suspended) | Email | `RiskManager` → `main.py` callback |
| Drawdown gate releases | Email | `RiskManager` |
| Kill switch activated | Email | `_evaluate()` |
| Reconciliation mismatch (orphan / cancel) | Email | `_reconcile_on_start()` |
| Order INVALID or unexpected CANCELED on exit | Email | `on_order_event` |
| Daily summary: open positions, equity, pending count | Email (once daily) | end of `_evaluate()` |

Notification recipients live in `config.py` as `NOTIFY_EMAIL_RECIPIENTS: Final[tuple[str, ...]]`.

---

## Required Config Additions

```python
# config.py — new constants for go-live
LIVE_BROKERAGE: Final[str] = "INTERACTIVE_BROKERS"
LIVE_ACCOUNT_TYPE: Final[str] = "MARGIN"
RECONCILE_ORPHAN_POLICY: Final[str] = "flatten"  # or "adopt_as_single_leg"
PENDING_ORDER_TTL_DAYS: Final[int] = 1
NOTIFY_EMAIL_RECIPIENTS: Final[tuple[str, ...]] = ()  # populated per-deployment
KILL_SWITCH_KEY: Final[str] = "power_trend/kill_switch"
STATE_STORE_KEY_TRADES: Final[str] = "power_trend/trades"
STATE_STORE_KEY_PENDING: Final[str] = "power_trend/pending_orders"
STATE_STORE_KEY_HWM: Final[str] = "power_trend/risk_hwm"
```

---

## Test Requirements (per safeguard)

| Safeguard | Test file | Key invariant |
|---|---|---|
| 1 — State | `tests/unit/test_state_store.py` | `save → load` round-trips trades, pending, HWM |
| 2 — Reconciliation | `tests/unit/test_reconciliation.py` | Orphan holding flattens (default policy); unknown open order cancels |
| 3 — Lifecycle | `tests/unit/test_order_lifecycle.py` | INVALID pops pending; PARTIALLY_FILLED accumulates; CANCELED on exit fires notify |
| 4 — GC | `tests/unit/test_pending_gc.py` | Pending entry older than `PENDING_ORDER_TTL_DAYS` is removed and broker cancel is attempted |
| 5 — Kill switch | `tests/integration/test_kill_switch.py` | Setting key blocks new entries; exits still run |
| 6 — Alerting | covered by handlers above with notify spy in `conftest.py` | Each mandatory event triggers a notify call |

All new tests use the `mock_algorithm` pattern in [tests/conftest.py](tests/conftest.py)
with an extended fake exposing `object_store`, `notify`, `transactions`, and
`portfolio` interfaces.

---

## Handoff Menu

| Next Step | Trigger | Skill |
|---|---|---|
| Author a specific handler from this spec | "implement state_store", "implement reconciliation" | `lifecycle-workflows/implement-handler` |
| Write the tests | "write tests for state_store" etc. | `lifecycle-workflows/write-unit-tests` |
| Move to paper-trade soak | "ready for paper", "deploy paper" | `lifecycle-workflows/go-live` (Phase 3) |
| Diagnose a soak-detected failure | "why no trades", "silent failure" | `debugging` |

---

## Reference Files

- [Architecture rules](../../_shared/references/architecture-rules.md)
- [Config thresholds](../../_shared/references/config-thresholds.md)
- [Handler responsibilities](../../_shared/references/handler-responsibilities.md)
- QC live-trading docs (RAG): `poetry run python rag/inject_context.py --query "<topic>"`
  - `"object store persist state restart"`
  - `"order lifecycle invalid canceled partially filled"`
  - `"notifications email web telegram"`
  - `"reconciliation OOS divergence"`
