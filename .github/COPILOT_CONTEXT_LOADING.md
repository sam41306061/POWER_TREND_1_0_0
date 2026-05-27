# Copilot Context Loading Guide — Power Trend Algo 1

Load only what you need, when you need it. The dispatch table in
`.github/copilot-instructions.md` loads automatically (~700 tokens). Everything else —
skill files, reference docs, strategy spec — is loaded on demand only.

---

## Token Budgets (approximate)

| Context Type | Tokens | When Loaded |
|---|---|---|
| `copilot-instructions.md` dispatch table | ~700 | Every conversation (automatic) |
| One Tier 1 lifecycle SKILL.md | ~2–3k | When lifecycle workflow is invoked |
| One Tier 2 trading domain SKILL.md | ~1–2k | When trading rule is invoked |
| One `_shared/references/` file | ~400–700 | When any skill references it |
| `STRATEGY_OVERVIEW.md` | ~6k | Only when full strategy spec needed |
| `docs/RAG_CONTEXT.md` (generated) | ~4–8k | After running `inject_context.py` |
| **Typical working session** | **~8–15k** | **~50k+ tokens available for work** |

---

## Common Workflow Sequences

### Implementing a new handler
1. Say: `"implement handler — RegimeFilter"`
2. Copilot loads: `lifecycle-workflows/implement-handler/SKILL.md`
3. Skill references: `_shared/references/architecture-rules.md`, `config-thresholds.md`
4. Handoff: `"write tests"` → `lifecycle-workflows/write-unit-tests/SKILL.md`
5. Handoff: `"create PR"` → `lifecycle-workflows/create-pr/SKILL.md`

### Debugging no-trade behavior
1. Say: `"why isn't my algo trading"`
2. Copilot loads: `debugging/SKILL.md`
3. Follow the 4-phase diagnostic checklist
4. If regime issue: `"regime not activating"` → `trading/regime-filter-rules/SKILL.md`

### Interpreting a backtest
1. Say: `"analyze backtest"` + paste QC statistics output
2. Copilot loads: `lifecycle-workflows/run-backtest-analysis/SKILL.md`
3. Skill routes to the relevant trading domain skill based on symptom

### Understanding strategy rules
Say the trigger phrase to load exactly one domain skill:

| Say... | Loads... |
|---|---|
| `"regime filter"` or `"entries allowed"` | `trading/regime-filter-rules/SKILL.md` |
| `"entry rules"` or `"when to enter"` | `trading/entry-rules/SKILL.md` |
| `"exit rules"` or `"SMA breakdown"` | `trading/exit-rules/SKILL.md` |
| `"pyramiding"` or `"leg sizing"` | `trading/pyramiding-rules/SKILL.md` |
| `"drawdown gate"` or `"HWM"` | `trading/risk-rules/SKILL.md` |

---

## Loading Shared References

If Copilot needs constants or architecture rules without loading a full skill:

| Say... | Loads... |
|---|---|
| `"read config thresholds"` | `.github/skills/_shared/references/config-thresholds.md` |
| `"read architecture rules"` | `.github/skills/_shared/references/architecture-rules.md` |
| `"read handler responsibilities"` | `.github/skills/_shared/references/handler-responsibilities.md` |

---

## QC API Reference (RAG)

Before asking about specific QuantConnect APIs (indicators, scheduling, history, consolidators),
regenerate the RAG context for that topic:

```bash
poetry run python rag/inject_context.py --query "<your topic>" --top-k 5
```

Then say: `"read docs/RAG_CONTEXT.md and answer: <your question>"`

---

## Anti-Patterns

| Anti-Pattern | Why It Hurts | Better Approach |
|---|---|---|
| "Read all the skill files" | Fills context window before any work begins | Use a trigger phrase to load one skill at a time |
| Loading `STRATEGY_OVERVIEW.md` proactively | ~6k tokens for content that may not be needed | Load only when you need the Gherkin contract |
| Running `inject_context.py` for every question | ~4–8k tokens, slow | Only run before QC API-specific questions |
| Pasting entire LEAN log files | Fills context; AI loses track of the question | Paste the 20–30 relevant lines and describe the symptom |
| Skipping the dispatch table and asking freeform | Skills not invoked; AI reasons from general knowledge | Use trigger phrases to load the authoritative skill |
