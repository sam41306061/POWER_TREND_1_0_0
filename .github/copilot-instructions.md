# GitHub Copilot Instructions — Power Trend Algo 1

**Strategy:** Daily long-only trend-following on US equities. QQQ regime gate (Power Trend
classifier on EMA21/SMA50 counters). Top-200 universe by 20d dollar volume, monthly refresh.
Equal-size pyramid adds up to `PYRAMID_MAX_ADDS`. See [docs/STRATEGY_OVERVIEW.md](docs/STRATEGY_OVERVIEW.md)
for the full spec and Gherkin contract.

**Architecture rule:** `main.py` is the *only* file that imports the LEAN SDK. All handlers
are pure Python with `__init__(self, algorithm)` constructors and no LEAN imports.

---

## Skill Dispatch Table

Load a skill when the trigger phrase matches. Do **not** pre-load skills speculatively.

### Tier 1 — Lifecycle Workflow Skills

| Skill | Trigger Phrases | File |
|---|---|---|
| `implement-handler` | "implement handler", "scaffold handler", "build handler" | [SKILL.md](.github/skills/lifecycle-workflows/implement-handler/SKILL.md) |
| `write-unit-tests` | "write tests", "unit tests for", "test coverage" | [SKILL.md](.github/skills/lifecycle-workflows/write-unit-tests/SKILL.md) |
| `run-backtest-analysis` | "analyze backtest", "interpret backtest results", "Sharpe ratio" | [SKILL.md](.github/skills/lifecycle-workflows/run-backtest-analysis/SKILL.md) |
| `create-pr` | "create PR", "open pull request", "ready to merge" | [SKILL.md](.github/skills/lifecycle-workflows/create-pr/SKILL.md) |
| `go-live` | "go live", "deploy live", "paper trade", "production deploy", "live readiness" | [SKILL.md](.github/skills/lifecycle-workflows/go-live/SKILL.md) |

### Tier 2 — Handler Domain Skills

| Skill | Trigger Phrases | File |
|---|---|---|
| `regime-filter-rules` | "regime filter", "power trend state", "entries allowed", "QQQ gate" | [SKILL.md](.github/skills/trading/regime-filter-rules/SKILL.md) |
| `entry-rules` | "entry rules", "entry trigger", "pyramid add", "when to enter" | [SKILL.md](.github/skills/trading/entry-rules/SKILL.md) |
| `exit-rules` | "exit rules", "exit logic", "when to exit", "SMA breakdown" | [SKILL.md](.github/skills/trading/exit-rules/SKILL.md) |
| `pyramiding-rules` | "pyramiding", "leg sizing", "add-on entry", "position sizing" | [SKILL.md](.github/skills/trading/pyramiding-rules/SKILL.md) |
| `risk-rules` | "risk management", "drawdown gate", "account drawdown", "HWM" | [SKILL.md](.github/skills/trading/risk-rules/SKILL.md) |
| `operational-safeguards` | "state persistence", "object store", "restart reconciliation", "kill switch", "order lifecycle", "partial fills", "notify" | [SKILL.md](.github/skills/trading/operational-safeguards/SKILL.md) |
| `debugging` | "why isn't it trading", "diagnose", "silent failure", "no orders" | [SKILL.md](.github/skills/debugging/SKILL.md) |
| `performance` | "optimize", "slow", "performance audit", "Five Multipliers" | [SKILLS_INDEX.md](.github/skills/SKILLS_INDEX.md) |

---

## Development Pipeline

```
implement-handler → write-unit-tests → run-backtest-analysis → create-pr
```
Debugging: `debugging → apply-fix → create-pr`

All handoffs require user confirmation — no auto-chaining.

---

## JIT Context Sources

| Context | Say... | Location |
|---|---|---|
| Handler responsibilities | "read handler responsibilities" | [handler-responsibilities.md](.github/skills/_shared/references/handler-responsibilities.md) |
| Config constants + values | "read config thresholds" | [config-thresholds.md](.github/skills/_shared/references/config-thresholds.md) |
| Architecture + coding rules | "read architecture rules" | [architecture-rules.md](.github/skills/_shared/references/architecture-rules.md) |
| QC API reference | Run `poetry run python rag/inject_context.py --query "<topic>" --top-k 5` | `docs/RAG_CONTEXT.md` |
| Full strategy spec | "read strategy overview" | [docs/STRATEGY_OVERVIEW.md](docs/STRATEGY_OVERVIEW.md) |
| All skills | "show skills index" | [SKILLS_INDEX.md](.github/skills/SKILLS_INDEX.md) |
