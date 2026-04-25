.PHONY: test cover lint format rag-crawl rag-query clean

# ── Testing ───────────────────────────────────────────────────────────
test:
	poetry run pytest tests/unit/ -v

cover:
	poetry run pytest tests/unit/ -v --cov=handlers --cov-report=html
	@echo "Coverage report: htmlcov/index.html"

# ── Code Quality ──────────────────────────────────────────────────────
lint:
	poetry run mypy handlers/

format:
	poetry run black .
	poetry run isort .

# ── RAG Pipeline ──────────────────────────────────────────────────────
rag-crawl:
	poetry run python rag/pipelines/ingest_pipeline.py

rag-crawl-section:
	@test -n "$(SECTION)" || (echo "Usage: make rag-crawl-section SECTION=indicators" && exit 1)
	poetry run python rag/pipelines/ingest_pipeline.py --sections $(SECTION)

rag-query:
	@test -n "$(Q)" || (echo "Usage: make rag-query Q='option chain filtering'" && exit 1)
	poetry run python rag/inject_context.py --query "$(Q)" --top-k 5

# ── LEAN Cloud ────────────────────────────────────────────────────────
push:
	@test -n "$(PROJECT_ID)" || (echo "Usage: make push PROJECT_ID=12345" && exit 1)
	lean cloud push --project-id $(PROJECT_ID)

backtest:
	@test -n "$(PROJECT_ID)" || (echo "Usage: make backtest PROJECT_ID=12345" && exit 1)
	lean cloud backtest --project-id $(PROJECT_ID)

# ── Cleanup ───────────────────────────────────────────────────────────
clean:
	rm -rf htmlcov/ .mypy_cache/ __pycache__ handlers/__pycache__ tests/__pycache__
	find . -name "*.pyc" -delete
