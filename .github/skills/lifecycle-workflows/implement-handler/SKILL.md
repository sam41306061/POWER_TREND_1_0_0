---
name: implement-handler
description: |
  Scaffold or implement a new Power Trend handler following the architecture rules.
  Trigger phrases: "implement handler", "scaffold handler", "build handler", "write handler",
  "create handler", "new handler"
argument-hint: "Name of the handler to implement (e.g., regime_filter, entry_engine) and a brief description of its responsibility"
---

# Implement Handler — Power Trend Algo

## Philosophy

Every handler in this codebase is pure Python — no LEAN SDK imports. The dependency injection
pattern means handlers are fully unit-testable without a running `QCAlgorithm`. Following the
exact structural pattern is non-negotiable; deviation breaks the test suite and violates the
LEAN isolation guarantee.

**Hard boundaries:**
- No `from QuantConnect import ...` or `from AlgorithmImports import ...` inside any handler file
- All thresholds must come from `config.py` — never hardcode numbers
- Constructor signature is always `__init__(self, algorithm) -> None`
- Return types must be Python primitives or dataclasses — no LEAN types in return values

---

## Phase 1 — Load Context

Before writing code:

1. Read [architecture-rules.md](_shared/references/architecture-rules.md) — confirm constructor
   pattern and LEAN isolation rules
2. Read [handler-responsibilities.md](_shared/references/handler-responsibilities.md) — confirm
   which handler owns which behavior and there is no overlap with existing handlers
3. Read [config-thresholds.md](_shared/references/config-thresholds.md) — identify which
   constants this handler will consume
4. Read `type_stubs.py` — identify any LEAN type stubs needed (e.g., `Symbol`, `TradeBar`)

---

## Phase 2 — Scaffold the Handler File

Create `handlers/<handler_name>.py` with this structure:

```python
"""<HandlerName> — <one-line responsibility>

Source handler: handlers/<handler_name>.py
Config constants used: CONSTANT_A, CONSTANT_B
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from config import CONSTANT_A, CONSTANT_B

if TYPE_CHECKING:
    from type_stubs import QCAlgorithm  # type hints only — never imported at runtime


class HandlerName:
    def __init__(self, algorithm) -> None:
        self._algorithm = algorithm
        # initialise internal state here
```

**Checklist:**
- [ ] No LEAN SDK import at module level
- [ ] All thresholds imported from `config.py` by constant name
- [ ] `TYPE_CHECKING` guard used for any type hint imports from `type_stubs.py`
- [ ] Constructor stores `algorithm` as `self._algorithm`

---

## Phase 3 — Implement Business Logic

Implement handler methods following these rules:

- Use `self._algorithm.debug(...)` for logging — never `print()`
- Cache expensive computations keyed by `(symbol, date)` — see `DataHandler` for the canonical
  cache pattern
- Check `IsReady` on any indicator before reading `.current.value`
- Access other handlers via the references passed into `__init__`, not via `self._algorithm`

---

## Phase 4 — Register in `main.py`

1. Import the handler class at the top of `main.py` (the only file that may hold all imports)
2. Instantiate in `initialize()`:
   ```python
   self._handler = HandlerName(self)
   ```
3. Wire into the daily evaluation scheduled event at `DAILY_EVAL_TIME`

---

## Handoff Menu

| Next Step | Trigger | Skill |
|---|---|---|
| Write tests for this handler | "write tests", "unit tests" | `lifecycle-workflows/write-unit-tests` |
| Check strategy rules before implementing | "entry rules", "exit rules" | `trading/entry-rules` or `trading/exit-rules` |
| Run the backtest and interpret results | "analyze backtest" | `lifecycle-workflows/run-backtest-analysis` |
| Create a PR | "create PR", "ready to merge" | `lifecycle-workflows/create-pr` |

---

## Reference Files

- [Architecture rules](_shared/references/architecture-rules.md)
- [Handler responsibilities](_shared/references/handler-responsibilities.md)
- [Config thresholds](_shared/references/config-thresholds.md)
- [Full strategy spec](../../../../STRATEGY_OVERVIEW.md)
- `type_stubs.py`
