---
name: go-live
description: |
  End-to-end workflow for taking the Power Trend algo from a green backtest to live
  production trading on QuantConnect. Covers brokerage selection, live/backtest
  configuration splits, paper-trade soak protocol, reduced-size launch, and rollback.
  Trigger phrases: "go live", "deploy live", "live trading checklist", "paper trade",
  "production deploy", "launch algo", "ready for live", "live readiness"
argument-hint: "Describe the deployment phase you are entering (prep / paper / live launch / scale-up)"
---

# Go-Live Workflow — Power Trend Algo

## Philosophy

A green backtest is necessary but not sufficient for live trading. QC explicitly states:
*"There is no automatic state management of live strategies. We recommend algorithms
reconstruct state using WarmUp and History methods. Once warmed up, use the Object Store
to save the data for the next algorithm restart."* Live mode introduces async fills,
restart-on-deploy, partial fills, brokerage rejections, and OOS reconciliation drift —
none of which a backtest exercises. This skill enforces a phased ramp, never a flip.

**Hard boundaries:**
- Never go live without completing the paper-trade soak in Phase 3
- Never launch at 100% intended capital — ramp 25% → 50% → 100%
- Never modify strategy parameters (`config.py` trading constants) during the ramp
- Never skip restart-resilience verification — QC redeploys/crashes are routine

---

## Phase 1 — Production Configuration Gaps

Verify these are addressed in `main.py` and `config.py` BEFORE any deploy attempt.
If any is missing, route to `trading/operational-safeguards`.

The **Paper soak** column marks items required for a QC Paper Trading soak (Phase 3).
The **Real broker** column marks items required only when moving to Interactive
Brokers / Alpaca / etc. for real-money launch (Phase 4+).

| Item | File | Paper soak | Real broker | Why |
|---|---|:---:|:---:|---|
| State persistence via `self.object_store` (`handlers/state_store.py`) | [main.py](main.py) | ✅ | ✅ | QC restarts paper and live nodes; in-memory state is wiped |
| Restart reconciliation against `self.portfolio` | [main.py](main.py) `_rehydrate_state()` | ✅ | ✅ | Broker is source of truth; drop stale rehydrated positions |
| `set_brokerage_model(...)` explicitly set | [main.py](main.py) `initialize()` | ⬜ | ✅ | QC Paper auto-applies; real brokers must be explicit |
| `set_cash` / `set_start_date` / `set_end_date` wrapped in `if not self.live_mode:` | [main.py](main.py) | ⬜ | ✅ | No-op in QC live mode; tidy-up only |
| `on_order_event` handles INVALID / CANCELED / PARTIALLY_FILLED | [main.py](main.py) | ⬜ | ✅ | QC Paper simulator behaves like backtest; real brokers reject |
| Pending-order stale GC (drop entries > 1 trading day old) | [main.py](main.py) `_evaluate()` | ⬜ | ✅ | Backstop for the row above |
| `self.notify.email` on drawdown trip / reconciliation mismatch / kill switch | [main.py](main.py) | ⬜ | ✅ | QC UI surfaces this for paper; live needs out-of-band alerts |
| Kill-switch read from `self.object_store` at top of `_evaluate()` | [main.py](main.py) | ⬜ | ✅ | QC UI stop is sufficient for paper; live wants no-redeploy pause |

---

## Phase 2 — Brokerage Selection

**Phase 3 soak target: QuantConnect Paper Trading** (`BrokerageName.QUANT_CONNECT_BROKERAGE`).
This is QC's internal simulator — no external broker account, no credentials, no
TWS / OAuth dance. Selectable from the QC deploy wizard's brokerage dropdown.
Use this for the full 4-week soak in Phase 3.

**Phase 4+ live launch target: Interactive Brokers**
(`BrokerageName.INTERACTIVE_BROKERS_BROKERAGE`, `AccountType.MARGIN`).
Only required when moving from paper to real money.

Confirm before promoting from QC Paper to IB:
- IB account tier supports the asset class (US equities — IB Pro is standard)
- Margin account type matches `MAX_POSITIONS_OPEN × INITIAL_LEG_SIZE_PCT × (1 + PYRAMID_MAX_ADDS)`
  expected deployment (≤ 32% gross → no leverage needed)
- 2FA reset/recovery codes captured
- IB credentials added to QC

Alternatives to IB for real-money launch (with explicit user approval):
Alpaca, Tradier. Coinbase (crypto — out of scope here).

Reference: query the RAG for brokerage-specific notes
```
poetry run python rag/inject_context.py --query "interactive brokers authentication account paper deploy"
```

---

## Phase 3 — Paper-Trade Soak (minimum 4 weeks)

Deploy to a **QC Paper Trading** node (brokerage = `QUANT_CONNECT_BROKERAGE`,
selected from the QC deploy wizard — no external account required). The algo
relies on `handlers/state_store.py` to persist position book, HWM, and regime
counters across forced redeploys.

Track these every trading day:

- [ ] Algorithm warmed up on restart and resumed without manual intervention
- [ ] Daily `_evaluate()` callback fires at `DAILY_EVAL_TIME` (09:35 ET)
- [ ] Open position count never exceeds `MAX_POSITIONS_OPEN`
- [ ] Pyramid leg count per symbol never exceeds `PYRAMID_MAX_ADDS + 1`
- [ ] HWM and drawdown gate persist across at least one **forced redeploy**
      (state_store rehydration must restore `active_trades`, `hwm`, and regime
      state from ObjectStore)
- [ ] Reconciliation: paper equity curve tracks the parallel OOS backtest within ±5%
      over the soak window
- [ ] At least one full universe refresh (`UNIVERSE_REFRESH_DAYS = 14`) completes cleanly

**Blockers (must fix before promoting to real-broker live launch):**
- Any `Insufficient buying power` log (the Feb-2021 backtest bug class)
- Any open-position count > `MAX_POSITIONS_OPEN`
- State rehydration failure after a forced redeploy (stuck broker positions the
  algo no longer tracks, or duplicate orders on restart)
- Reconciliation drift > 5% with no identifiable cause (data, fees, slippage)

QC OOS reconciliation note: *"If your algorithm is perfectly reconciled, it has an
exact overlap between its live and OOS backtest equity curves. Deviations mean the
performance has differed."* — surface deviations early.

---

## Phase 4 — Reduced-Size Live Launch

Stage progression (2 weeks per stage minimum, no anomalies):

| Stage | Capital | Gate to advance |
|---|---|---|
| 4A | 25% of intended | Zero buying-power errors, zero reconciliation alerts |
| 4B | 50% of intended | Equity tracks OOS within ±3%, no manual interventions |
| 4C | 100% of intended | Two clean weeks at 50%, all monitoring alerts triaged |

During the ramp:
- Daily review of QC live results page + OOS overlay
- Weekly review of `_trades` log vs. brokerage statements
- Do not change `config.py` trading constants. Operational constants (kill switch,
  notification recipients) are allowed.

---

## Phase 5 — Steady-State Operations

- Weekly: review fills, drawdown, regime state distribution
- Monthly: re-run a fresh backtest from `LIVE_LAUNCH_DATE` forward and overlay against
  realized live curve; investigate any >5% divergence
- Quarterly: re-crawl QC live-trading RAG section (`--force`) and review any
  brokerage / API changes
- Rollback procedure: stop algo via QC UI → flatten via brokerage UI (NOT via algo
  liquidation) → archive logs → triage in dev environment

---

## Handoff Menu

| Next Step | Trigger | Skill |
|---|---|---|
| Build the operational safeguards (state, reconciliation, kill switch) | "state persistence", "reconciliation", "kill switch" | `trading/operational-safeguards` |
| Add or update unit tests for go-live code | "test coverage", "unit tests for state_store" | `lifecycle-workflows/write-unit-tests` |
| Diagnose a paper-soak anomaly | "why no trades", "silent failure" | `debugging` |
| Open PR for go-live readiness changes | "create PR" | `lifecycle-workflows/create-pr` |

---

## Reference Files

- [Architecture rules](../../_shared/references/architecture-rules.md)
- [Config thresholds](../../_shared/references/config-thresholds.md)
- [Handler responsibilities](../../_shared/references/handler-responsibilities.md)
- [Strategy overview](../../../../docs/STRATEGY_OVERVIEW.md)
- QC live-trading docs (RAG): `poetry run python rag/inject_context.py --query "<topic>"`
