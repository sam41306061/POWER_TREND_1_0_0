# SKILLS_INDEX — Power Trend Algo 1

Master index of all skills. Load by trigger phrase — do not pre-load all skills at startup.

**Development pipeline:**
```
implement-handler → write-unit-tests → run-backtest-analysis → create-pr
```
Debugging: `debugging → apply-fix → create-pr`

---

## Tier 1 — Lifecycle Workflow Skills

| Skill | Trigger Phrases | Status | File |
|---|---|---|---|
| `implement-handler` | "implement handler", "scaffold handler", "build handler" | ✅ Populated | [SKILL.md](lifecycle-workflows/implement-handler/SKILL.md) |
| `write-unit-tests` | "write tests", "unit tests for", "test coverage" | ✅ Populated | [SKILL.md](lifecycle-workflows/write-unit-tests/SKILL.md) |
| `run-backtest-analysis` | "analyze backtest", "interpret results", "Sharpe ratio" | ✅ Populated | [SKILL.md](lifecycle-workflows/run-backtest-analysis/SKILL.md) |
| `create-pr` | "create PR", "open pull request", "ready to merge" | ✅ Populated | [SKILL.md](lifecycle-workflows/create-pr/SKILL.md) |

---

## Tier 2 — Handler Domain Skills

### trading/ — Power Trend Strategy Rules

| Skill | Trigger Phrases | Status | File |
|---|---|---|---|
| `regime-filter-rules` | "regime filter", "power trend state", "entries allowed", "QQQ gate" | ✅ Populated | [SKILL.md](trading/regime-filter-rules/SKILL.md) |
| `entry-rules` | "entry rules", "entry trigger", "pyramid add", "when to enter" | ✅ Populated | [SKILL.md](trading/entry-rules/SKILL.md) |
| `exit-rules` | "exit rules", "exit logic", "when to exit", "SMA breakdown" | ✅ Populated | [SKILL.md](trading/exit-rules/SKILL.md) |
| `pyramiding-rules` | "pyramiding", "leg sizing", "add-on entry", "position sizing" | ✅ Populated | [SKILL.md](trading/pyramiding-rules/SKILL.md) |
| `risk-rules` | "risk management", "drawdown gate", "account drawdown", "HWM" | ✅ Populated | [SKILL.md](trading/risk-rules/SKILL.md) |

### debugging/

| Skill | Trigger Phrases | Status | File |
|---|---|---|---|
| `debugging` | "why isn't it trading", "diagnose", "silent failure", "no orders" | ✅ Populated | [SKILL.md](debugging/SKILL.md) |
| — | *(loaded by debugging skill)* | 📚 Reference | [why_didnt_my_algo_trade.md](debugging/reference/why_didnt_my_algo_trade.md) |
| — | *(loaded by debugging skill)* | 📚 Reference | [silent_failure_modes.md](debugging/reference/silent_failure_modes.md) |

### performant_software/

| Skill | Trigger Phrases | Status | File |
|---|---|---|---|
| `five-multipliers` | "optimize", "performance framework", "Five Multipliers" | ✅ Populated | [five_multipliers.md](performant_software/five_multipliers.md) |
| `waste-and-instructions` | "reduce instructions", "eliminate waste", "Python overhead" | ✅ Populated | [waste_and_instructions.md](performant_software/waste_and_instructions.md) |
| `ipc-dependency-chains` | "IPC", "dependency chains", "instruction-level parallelism" | ✅ Populated | [ipc_dependency_chains.md](performant_software/ipc_dependency_chains.md) |
| `simd-vectorization` | "SIMD", "vectorize", "NumPy optimization" | ✅ Populated | [simd_vectorization.md](performant_software/simd_vectorization.md) |
| `memory-caching` | "cache efficiency", "memory hierarchy", "L1/L2 cache" | ✅ Populated | [memory_hierarchy_and_caching.md](performant_software/memory_hierarchy_and_caching.md) |
| `multithreading` | "multithreading", "ProcessPoolExecutor", "GIL" | ✅ Populated | [multithreading.md](performant_software/multithreading.md) |
| `measuring-performance` | "measure performance", "profiling", "bandwidth ceiling" | ✅ Populated | [measuring_performance.md](performant_software/measuring_performance.md) |

---

## _shared/references/ — Cross-Cutting Reference Files

Consumed JIT by multiple skills — not direct invocation targets. Say the trigger phrase to load.

| File | Say... | File |
|---|---|---|
| Config thresholds | "read config thresholds" | [config-thresholds.md](_shared/references/config-thresholds.md) |
| Architecture rules | "read architecture rules" | [architecture-rules.md](_shared/references/architecture-rules.md) |
| Handler responsibilities | "read handler responsibilities" | [handler-responsibilities.md](_shared/references/handler-responsibilities.md) |
| RAG pipeline | "read RAG structure", "how does the RAG work", "inject context" | [AI_RAG_STRUCTURE.md](../../docs/AI_RAG_STRUCTURE.md) |

---

## Not In Scope

| Domain | Reason |
|---|---|
| `options/` — option_chain_filtering.md | Power Trend is equity-only; file is a template carryover |

---

## Legend

- ✅ **Populated** — content is current and authoritative
- 📚 **Reference** — supporting reference document; not directly invocable as a skill
- 📋 **Stub** — registered but file not yet created

---

## Adding a New Skill

1. Create `.github/skills/<tier>/<skill-name>/SKILL.md` with:
   - YAML frontmatter (`name`, `description` with trigger phrases, `argument-hint`)
   - Philosophy + hard boundaries
   - 4–6 phased workflow steps
   - Handoff Menu table
   - Reference Files section
2. Register it in this index with tier, trigger phrases, and status
3. Add a dispatch row to `.github/copilot-instructions.md`

All three steps are required — an unregistered skill is invisible to the AI.
