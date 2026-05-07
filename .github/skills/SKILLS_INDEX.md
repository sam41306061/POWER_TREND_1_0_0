# SKILLS_INDEX — <!-- TODO: Project Name -->

Master index of all behavioral-invariant skill files. These files define the contracts
that tests enforce. Consult them before modifying any handler.

---

## lifecycle/

| File | Status | Description |
|---|---|---|
| [warmup_and_readiness.md](lifecycle/warmup_and_readiness.md) | ✅ Populated | Handler init order, daily schedule phases, fill reconciliation |
| [algo_lifecycle_rules.md](lifecycle/algo_lifecycle_rules.md) | ✅ Populated | initialize(), on_data(), on_order_event(), scheduled events, warm-up guard |

## indicators/

| File | Status | Description |
|---|---|---|
| [indicator_caching_rules.md](indicators/indicator_caching_rules.md) | ✅ Populated | Cache key structure, EMA seeding, ATR computation invariants |
| [multi_timeframe_indicators.md](indicators/multi_timeframe_indicators.md) | ✅ Populated | Native vs manual computation, consolidators, multi-symbol management |
| [indicator_readiness_gates.md](indicators/indicator_readiness_gates.md) | ✅ Populated | IsReady behaviour, set_warm_up, history injection, min bar requirements |

## data/

| File | Status | Description |
|---|---|---|
| [data_alignment_invariants.md](data/data_alignment_invariants.md) | ✅ Populated | Dual-format support, column naming, chronological ordering |
| [consolidation_rules.md](data/consolidation_rules.md) | ✅ Populated | TradeBar/QuoteBar consolidators, DataNormalizationMode, history alignment |

## options/

| File | Status | Description |
|---|---|---|
| [option_chain_filtering.md](options/option_chain_filtering.md) | ✅ Populated | Contract selection flow, OI gate, IV analytics, delta extraction |

## trading/

<!-- TODO: Add strategy-specific trading skill files -->

| File | Status | Description |
|---|---|---|
| | 📋 Stub | Create files for your strategy's validation rules |
| | 📋 Stub | Create files for your position management state machine |

## debugging/

| File | Status | Description |
|---|---|---|
| [why_didnt_my_algo_trade.md](debugging/why_didnt_my_algo_trade.md) | ✅ Populated | Phase 1/2 gate checklist, order rejection causes, data issues |
| [silent_failure_modes.md](debugging/silent_failure_modes.md) | ✅ Populated | Cache, empty dict, options chain, scheduling, fill reconciliation |

## backtesting/

| File | Status | Description |
|---|---|---|
| [results_interpretation.md](backtesting/results_interpretation.md) | ✅ Populated | Runtime statistics, key metrics (Sharpe/PSR/drawdown), charts |
| [overfitting_prevention.md](backtesting/overfitting_prevention.md) | ✅ Populated | Hypothesis-driven research, parameter detection, backtest count limits |
| [deployment_constraints.md](backtesting/deployment_constraints.md) | ✅ Populated | Node specs, RAM/log/order/chart quotas, runtime limits |
| [debugging_backtests.md](backtesting/debugging_backtests.md) | ✅ Populated | QC debugger workflow, breakpoints, variable inspection |

---

## Legend

- ✅ **Populated** — content derived from actual handler source; authoritative
- 📋 **Stub** — headings in place; populate as you implement handlers

---

## Adding a New Skill File

1. Create the file in the appropriate subdirectory
2. Add it to this index with status and description
3. Reference any `config.py` constants by their exact name
4. Link the source handler(s) in the file header
