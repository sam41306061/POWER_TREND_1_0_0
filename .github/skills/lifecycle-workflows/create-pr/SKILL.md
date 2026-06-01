---
name: create-pr
description: |
  Run the four-check quality gate and create a pull request for the Power Trend Algo.
  Trigger phrases: "create PR", "open pull request", "ready to merge", "submit PR",
  "create pull request", "push PR"
argument-hint: "Branch name and a one-line description of the change (e.g., 'feat/regime-filter — implements RegimeFilter handler')"
---

# Create PR — Power Trend Algo

## Philosophy

No code reaches `main` without passing all four quality checks. The gate is not optional even
for small changes — a config drift or an accidental LEAN import can silently break the backtest.

**Hard boundaries:**
- Never bypass with `--no-verify` or by skipping individual checks
- Do not open a PR from `main` — always work from a feature branch
- Branch naming: `feat/<description>`, `fix/<description>`, or `refactor/<description>`
- Coverage must be ≥ 80% on the handler(s) changed — not just the repo average

---

## Phase 1 — Confirm Branch

```bash
git branch --show-current
```

If on `main`, stop: create a feature branch first with `git checkout -b feat/<description>`.

---

## Phase 0 — Spec / Config / Skills Sync

**Run this first**, before any other quality check. A bare-number drift between the spec,
`config.py`, and the skill docs is a silent failure that the test suite cannot catch.

```bash
# Numbers in skill docs must match config.py
for name in MAX_POSITIONS_OPEN PYRAMID_MAX_ADDS INITIAL_LEG_SIZE_PCT STOP_LOSS_PCT \
            MAX_ACCOUNT_DRAWDOWN_PCT REGIME_EMA_PERIOD REGIME_SMA_PERIOD; do
  echo "=== $name ==="
  grep -rn "$name" config.py STRATEGY_OVERVIEW.md .github/skills/
done
```

Stop and fix if:
- A value appears in `STRATEGY_OVERVIEW.md` but a different value in `config.py`
- A value in `_shared/references/config-thresholds.md` is stale vs. `config.py`
- A per-skill SKILL.md cites a literal number that no longer matches `config.py`

Then verify aggregate exposure:

```bash
poetry run python -c "import config; config.validate_config(); print('OK')"
```

---

## Phase 2 — Run the Quality Gate (all 4 must pass)

Fix each failure before moving to the next check.

```bash
# 1. Format
poetry run black --check .

# 2. Lint
poetry run pylint handlers/

# 3. Tests + coverage
poetry run pytest tests/unit/ -v --cov=handlers --cov-report=term-missing --cov-fail-under=80

# 4. Hardcode check — no magic numbers in handler files
grep -rn "[0-9]\+" handlers/ | grep -v "config\." | grep -v "#" | grep -v "0\.0\b"
```

- **Black fails:** run `poetry run black .` to auto-format, re-check
- **Coverage fails:** load `write-unit-tests` skill to add missing test cases
- **Hardcode check flags a line:** move the value to `config.py` as a `Final` constant

---

## Phase 3 — Build PR Description

```markdown
## Summary
<One-sentence description of what changed and why>

## Handlers Changed
- `<handler_name>.py` — <what changed>

## Quality Gate
- [x] Black — passed
- [x] Pylint — passed (score: X.X/10)
- [x] Tests — passed (coverage: XX%)
- [x] No hardcoded thresholds

## Config Constants Used
- `CONSTANT_A` = <value>
- `CONSTANT_B` = <value>

## Testing
<How was this tested — unit tests, backtest run, manual QC log review>
```

---

## Phase 4 — Create the PR

```bash
git add -p          # review each hunk individually before staging
git commit -m "feat: <description>"
git push origin <branch-name>
gh pr create --title "feat: <description>" --body-file pr_body.md --draft
```

Review the draft PR before marking ready for review.

---

## Handoff Menu

| Next Step | Trigger | Skill |
|---|---|---|
| Fix failing tests before PR | "test failing", "coverage low" | `lifecycle-workflows/write-unit-tests` |
| Validate backtest before merging | "check backtest" | `lifecycle-workflows/run-backtest-analysis` |

---

## Reference Files

- [Architecture rules](_shared/references/architecture-rules.md)
- `pyproject.toml` — Black line length and Pylint configuration
