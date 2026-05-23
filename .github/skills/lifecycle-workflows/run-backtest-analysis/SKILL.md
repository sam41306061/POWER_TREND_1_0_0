---
name: run-backtest-analysis
description: |
  Interpret QuantConnect backtest results for the Power Trend Algo. Classify performance,
  identify overfitting signals, and route to the correct diagnostic skill.
  Trigger phrases: "analyze backtest", "interpret backtest results", "backtest output",
  "Sharpe ratio", "PSR", "drawdown metrics", "evaluate backtest", "interpret results"
argument-hint: "Paste the QC backtest statistics output or describe the metrics you want analyzed"
---

# Run Backtest Analysis — Power Trend Algo

## Philosophy

Backtests are hypotheses, not proofs. A passing backtest is necessary but not sufficient for a
good strategy. Overfit strategies show high in-sample Sharpe but fail live. This skill guides
structured interpretation of QC output and flags overfitting signals before any config tuning.

**Hard boundaries:**
- Do not change `config.py` thresholds based on a single backtest run
- Do not interpret Sharpe Ratio in isolation — always check PSR and drawdown together
- Do not run more than 5 parameter variants without documenting the hypothesis first

---

## Phase 1 — Collect Output

Paste or load the QC backtest statistics. Minimum required metrics:

- CAGR
- Sharpe Ratio
- Probabilistic Sharpe Ratio (PSR)
- Maximum Drawdown
- Win Rate
- Trade Count
- Net Profit

---

## Phase 2 — Score Against Benchmarks

| Metric | Target | Concern | Action if Concern |
|---|---|---|---|
| Sharpe Ratio | > 1.0 | < 0.5 | Investigate regime filter activation rate |
| PSR | > 95% | < 80% | Sample size too small; extend date range |
| Max Drawdown | < 20% | > 30% | Review exit priority order and stop loss level |
| CAGR | > 15% | < 8% | Review universe quality and pyramid sizing |
| Win Rate | 45–65% | > 75% | Possible data snooping; check hold period distribution |
| Trade Count | ≥ 50 | < 20 | Regime may be too restrictive; check counter thresholds |

---

## Phase 3 — Overfitting Checks

Run this checklist before trusting any result:

- [ ] Date range spans at least one full market cycle (bull + correction + recovery)
- [ ] Fewer than 5 free parameters tuned to this dataset
- [ ] Trade count ≥ 50 (statistical significance floor)
- [ ] Out-of-sample segment tested separately (e.g., hold out the most recent 2 years)
- [ ] Regime filter activation rate is reasonable — not always on or always off
- [ ] Walk-forward or Monte Carlo test does not show performance collapse

---

## Phase 4 — Diagnose Underperformance

Route to the correct domain skill based on the symptom:

| Symptom | Likely Cause | Next Skill |
|---|---|---|
| Very few trades, low CAGR | Regime rarely activates | `trading/regime-filter-rules` |
| High drawdown, low win rate | Exit logic firing too late | `trading/exit-rules` |
| Good Sharpe but low CAGR | Position sizing too conservative | `trading/pyramiding-rules` |
| Drawdown gate triggered frequently | HWM suspending entries often | `trading/risk-rules` |
| Strategy not reaching max pyramid depth | Entry trigger too strict | `trading/entry-rules` |

---

## Handoff Menu

| Next Step | Trigger | Skill |
|---|---|---|
| Investigate a specific handler's logic | "regime not activating", "wrong exits" | relevant `trading/` skill |
| Create a PR for the backtest branch | "create PR" | `lifecycle-workflows/create-pr` |
| Debug algo behavior before backtesting | "diagnose", "why no trades" | `debugging` |

---

## Reference Files

- [Config thresholds](_shared/references/config-thresholds.md)
- [Full strategy spec + Gherkin contract](docs/STRATEGY_OVERVIEW.md)
