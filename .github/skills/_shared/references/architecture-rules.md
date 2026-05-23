# Architecture Rules & Coding Guidelines

**Source:** `copilot-instructions.md`, `docs/DEVELOPMENT_GUIDE.md`
**Load when:** implementing or modifying any handler; reviewing PRs; setting up a new handler

---

## Core Architecture Constraints

1. **LEAN isolation** — `main.py` is the *only* file that imports the LEAN SDK
   (`AlgorithmImports`). All business logic lives in `handlers/` as pure Python, fully
   testable without LEAN.

2. **Dependency injection** — Every handler receives `algorithm` (the `QCAlgorithm` reference)
   in its `__init__(self, algorithm)` constructor. Never import LEAN types inside handlers.

3. **Single source of truth for config** — All strategy thresholds belong in `config.py` as
   `Final` typed constants. Never hardcode values in handlers or tests.

4. **Test doubles** — `type_stubs.py` provides stub implementations of all LEAN types used in
   tests. Use these patterns when a handler needs a new LEAN type reference.

---

## Handler Constructor Pattern

```python
class MyHandler:
    def __init__(self, algorithm) -> None:
        self._algorithm = algorithm
        # import constants from config, never hardcode
```

---

## Coding Standards

| Rule | Detail |
|---|---|
| Line length | 100 characters (Black-enforced via `pyproject.toml`) |
| Formatter | `poetry run black .` |
| Linter | `poetry run pylint handlers/` |
| Test coverage | ≥ 80% per handler — `poetry run pytest tests/unit/ -v --cov` |
| No LEAN imports in handlers | Any `from QuantConnect` in a handler file is a bug |
| No hardcoded thresholds | All constants must reference `config.py` by name |

---

## Test File Pattern

```python
from handlers.my_handler import MyHandler
from config import CONSTANT_A


def test_something(mock_algorithm):
    handler = MyHandler(mock_algorithm)
    # assert behavior
```

`mock_algorithm` fixture is defined in `tests/conftest.py`.

---

## Type Hint Pattern for LEAN Types

```python
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from type_stubs import QCAlgorithm  # only for type hints — never at runtime
```

The `TYPE_CHECKING` guard ensures LEAN stubs are never imported in a running LEAN environment.
