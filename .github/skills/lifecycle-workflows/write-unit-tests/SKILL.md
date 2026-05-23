---
name: write-unit-tests
description: |
  Write pytest unit tests for a Power Trend handler in tests/unit/.
  Trigger phrases: "write tests", "unit tests for", "test coverage", "write unit tests",
  "add tests", "test this handler", "test coverage"
argument-hint: "Name of the handler to test (e.g., regime_filter, entry_engine) and the behaviors to cover"
---

# Write Unit Tests — Power Trend Algo

## Philosophy

Handlers are pure Python — tests never need a running LEAN instance. The `type_stubs.py` module
provides all necessary LEAN type doubles. Tests must achieve ≥ 80% coverage per handler. Each
test verifies a single behavioral invariant: one scenario, one assertion.

**Hard boundaries:**
- Never instantiate `QCAlgorithm` directly — use the `mock_algorithm` fixture from `conftest.py`
- Never call the real LEAN history API in tests — inject synthetic data dictionaries
- Tests live in `tests/unit/test_<handler_name>.py` only
- No magic numbers — all thresholds referenced by config constant name

---

## Phase 1 — Load Context

1. Read `tests/conftest.py` — understand the `mock_algorithm` fixture and available helpers
2. Read the handler source file in full — identify all public methods and state transitions
3. Read [config-thresholds.md](_shared/references/config-thresholds.md) — note which constants
   affect branching behavior (these become boundary-value test parameters)

---

## Phase 2 — Identify Test Cases

For each public method, derive cases from this invariant matrix:

| Condition | Happy path | Boundary (n vs n-1) | Sad path |
|---|---|---|---|
| Regime: `entries_allowed()` | All counters at threshold | Counter at threshold - 1 | SMA50 declining |
| Entry: trigger fires | All 5 conditions true | `close` exactly at `EMA21` | `EMA21` below `SMA50` |
| Exit: stop loss fires before SMA breakdown | `close < avg_cost × 0.93` | `close` exactly at stop | No breakdown |
| Risk: drawdown gate | Drawdown ≥ 15% | Drawdown at 14.9% | Portfolio at HWM |

Always test:
- The exact boundary value (e.g., counter `== LOW_ABOVE_EMA_DAYS` vs `== LOW_ABOVE_EMA_DAYS - 1`)
- State after a reset (counters back to 0 after regime exits `TREND_UP`)
- `None` / missing data inputs (cache miss, indicator not ready)

---

## Phase 3 — Write the Test File

File: `tests/unit/test_<handler_name>.py`

```python
import pytest
from handlers.<handler_name> import HandlerName
from config import CONSTANT_A, CONSTANT_B


@pytest.fixture
def handler(mock_algorithm):
    return HandlerName(mock_algorithm)


def test_<behavior>_when_<condition>(handler):
    # Arrange — build the minimal data dict the handler needs
    data = {"close": 100.0, "EMA21": 98.0, "SMA50": 95.0, ...}
    # Act
    result = handler.method(data)
    # Assert
    assert result == expected
```

**Checklist:**
- [ ] One assertion per test function (SRP)
- [ ] Test names follow `test_<behavior>_when_<condition>` pattern
- [ ] All config constants referenced by name, not magic number
- [ ] Both boundary values tested for every counter threshold
- [ ] Sad path and `None`-input cases covered

---

## Phase 4 — Verify Coverage

```bash
poetry run pytest tests/unit/test_<handler_name>.py -v \
    --cov=handlers.<handler_name> \
    --cov-report=term-missing
```

- Coverage must be ≥ 80% for the handler under test
- Review the "missing" column — add tests for uncovered branches
- Full suite sanity check: `poetry run pytest tests/unit/ -v`

---

## Handoff Menu

| Next Step | Trigger | Skill |
|---|---|---|
| Run a backtest with the implemented handler | "analyze backtest" | `lifecycle-workflows/run-backtest-analysis` |
| Create a PR | "create PR", "ready to merge" | `lifecycle-workflows/create-pr` |
| Debug a failing test | "test failing", "assertion error" | `debugging` |

---

## Reference Files

- [Architecture rules](_shared/references/architecture-rules.md)
- [Config thresholds](_shared/references/config-thresholds.md)
- `tests/conftest.py`
- `type_stubs.py`
