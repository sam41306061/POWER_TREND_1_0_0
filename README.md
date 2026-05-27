# lean-algo-template

Reusable scaffold for QuantConnect LEAN algorithm projects. Provides a modular handler
architecture, full RAG documentation pipeline, AI skills files, and test infrastructure
— all strategy-agnostic and ready to customize.

---

## Quick Start

```bash
# 1. Clone or use as template
git clone <this-repo> my-strategy && cd my-strategy

# 2. Install dependencies
poetry install

# 3. Run template tests to verify setup
poetry run pytest tests/unit/ -v

# 4. Start building — see docs/DEVELOPMENT_GUIDE.md for the full sequence
```

---

## Architecture

```
main.py  ─────────────  LEAN SDK (only file that imports it)
   │
   ├── handlers/       Pure Python business logic (DI pattern)
   ├── config.py       All parameters as Final[...] constants
   ├── type_stubs.py   LEAN type mocks for local testing
   └── tests/          Unit tests with module injection
```

**Key rule:** Only `main.py` imports the LEAN SDK. All handlers receive the algorithm
object via constructor injection and are fully testable without LEAN.

See [docs/FILE_MAP.md](docs/FILE_MAP.md) for detailed module responsibilities.

---

## What's Included

### Core Infrastructure (use as-is)
- **`type_stubs.py`** — Complete LEAN type mocks (Symbol, QCAlgorithm, OptionContract, etc.)
- **`tests/conftest.py`** — Module injection, shared fixtures (mock_algorithm, mock_indicators, etc.)
- **RAG pipeline** — Playwright crawler → BM25 index → Copilot context injection

### Application Templates (customize per strategy)
- **`config.py`** — Parameter structure with validation; fill in your thresholds
- **`main.py`** — LEAN lifecycle skeleton with phase-based scheduling
- **`handlers/`** — Stub handlers showing the DI pattern and method contracts
- **`universe/candidates.csv`** — Symbol list template

### AI Context Layer
- **`docs/skills/`** — 14 behavioral skill files covering QC lifecycle, indicators, data,
  options, debugging, and backtesting
- **`.github/copilot-instructions.md`** — AI assistant context template
- **RAG pipeline** — Query QC docs directly: `poetry run python rag/inject_context.py --query "..."`

### Documentation Templates
- [STRATEGY_OVERVIEW.md](STRATEGY_OVERVIEW.md) — Strategy thesis and system flow
- [FILE_MAP.md](docs/FILE_MAP.md) — Module map and data flow
- [DEVELOPMENT_GUIDE.md](docs/DEVELOPMENT_GUIDE.md) — Build sequence and conventions
- [IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) — Phase-by-phase plan
- [CHECKLIST_TEMPLATE.md](docs/CHECKLIST_TEMPLATE.md) — Operational checklist
- [PLATFORM_ADAPTERS.md](docs/PLATFORM_ADAPTERS.md) — Porting to non-QC platforms

---

## Project Structure

```
├── main.py                     # LEAN orchestrator (customize)
├── config.py                   # Strategy parameters (customize)
├── type_stubs.py               # LEAN mocks (use as-is)
├── handlers/                   # Business logic handlers (customize)
│   ├── _example_handler.py     # Pattern reference
│   ├── universe_filter.py
│   ├── data_handler.py
│   ├── technical_validator.py
│   ├── setup_checker.py
│   ├── instrument_selector.py
│   ├── position_manager.py
│   └── option_analytics.py
├── tests/
│   ├── conftest.py             # Module injection + fixtures (use as-is)
│   └── unit/                   # Unit tests (customize)
├── docs/                       # Documentation templates
│   └── skills/                 # AI behavioral skill files
├── rag/                        # RAG documentation pipeline (use as-is)
│   ├── inject_context.py       # CLI query tool
│   ├── crawler/                # Playwright crawler
│   ├── processing/             # HTML → Markdown → chunks
│   ├── storage/                # DocStore + BM25 index
│   └── pipelines/              # Ingest orchestration
├── adapters/                   # Platform adapter examples
├── universe/                   # Candidate symbol lists
└── .github/                    # AI assistant config
```

---

## Common Commands

```bash
# Run tests
poetry run pytest tests/unit/ -v

# Run tests with coverage
poetry run pytest tests/unit/ -v --cov=handlers --cov-report=html

# Format code
poetry run black .

# Type check
poetry run mypy handlers/

# RAG: crawl QC docs
poetry run python rag/pipelines/ingest_pipeline.py --sections indicators lifecycle

# RAG: query corpus
poetry run python rag/inject_context.py --query "your topic" --top-k 5

# Push to LEAN Cloud
lean cloud push --project-id <PROJECT_ID>
```

---

## Getting Started with a New Strategy

1. **Fill in `config.py`** — Define your strategy's parameters and thresholds
2. **Update `universe/candidates.csv`** — Add your target symbols
3. **Implement handlers** — Follow the patterns in `_example_handler.py`
4. **Write tests** — Use the fixtures in `conftest.py`
5. **Wire `main.py`** — Connect handlers to LEAN lifecycle callbacks
6. **Update docs** — Fill in the `<!-- TODO -->` markers in doc templates
7. **Set up RAG** — Enable relevant QC doc sections in `rag/crawler/config.py`

See [docs/DEVELOPMENT_GUIDE.md](docs/DEVELOPMENT_GUIDE.md) for the full build sequence.

---

## License

<!-- TODO: Add your license -->
