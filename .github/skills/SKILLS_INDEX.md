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

| File | Status | Description |
|---|---|---|
| [webby_rsi.md](trading/webby_rsi.md) | ✅ Populated | Webby RSI 2.0: three components (`atr_stretch_low`, `high_vs_ema21`, `high_vs_sma10`), ATR windows, stretch/trim rule |
| [power_trend.md](trading/power_trend.md) | ✅ Populated | Power Trend state machine (4-rule strict vs lite), state table, re-activation policy, Webby RSI during trend |
| [order_management.md](trading/order_management.md) | ✅ Populated | Exit priority waterfall (Priority 0 stretch-trim through Priority 4), sizing rules, re-entry checklist |

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

## bugs_and_lessons/

| File | Status | Description |
|---|---|---|
| [silent_position_exit_failure.md](bugs_and_lessons/silent_position_exit_failure.md) | ✅ Populated | Two-gate silent exit failure: history fetch + security lookup. Stop loss bypassed for delisted/dropped symbols. Cascade: position lock-up → cap full → zero new entries → Sharpe 0.038. Log tags: `[DATA CRITICAL]`, `[EXIT CRITICAL]`, `[EXIT WARN]`, `[EXIT SIGNAL]`, `[REGIME TRANSITION]` |

## performant_software/

| File | Status | Description |
|---|---|---|
| [five_multipliers.md](performant_software/five_multipliers.md) | ✅ Populated | Framework overview — the two levers and five multipliers; correct order of attack |
| [waste_and_instructions.md](performant_software/waste_and_instructions.md) | ✅ Populated | Multiplier 1 — eliminating unnecessary instructions; Python interpreter overhead; builtins and typed arrays |
| [ipc_dependency_chains.md](performant_software/ipc_dependency_chains.md) | ✅ Populated | Multiplier 2 — serial dependency chains; multiple-accumulator fix; loop overhead |
| [simd_vectorization.md](performant_software/simd_vectorization.md) | ✅ Populated | Multiplier 3 — SIMD lanes; NumPy as on-ramp; what kills vectorization |
| [memory_hierarchy_and_caching.md](performant_software/memory_hierarchy_and_caching.md) | ✅ Populated | Multiplier 4 — cache tiers; sequential access; struct-of-arrays; chunking |
| [multithreading.md](performant_software/multithreading.md) | ✅ Populated | Multiplier 5 — separability; super-linear cache effect; GIL and ProcessPoolExecutor |
| [measuring_performance.md](performant_software/measuring_performance.md) | ✅ Populated | Cross-cutting — latency vs throughput; bandwidth ceiling; repetition testing; profiling workflow |

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
