"""rag/crawler/config.py — Crawler configuration for the RAG pipeline.

Paths, crawler behaviour, and URL sections to crawl.
"""

from pathlib import Path
from typing import Final

# =============================================================================
# Paths
# =============================================================================

RAG_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
DATA_DIR: Final[Path] = RAG_ROOT / "data"
RAW_DIR: Final[Path] = DATA_DIR / "raw"
DOC_STORE_PATH: Final[Path] = DATA_DIR / "doc_store.json"
BM25_CORPUS_PATH: Final[Path] = DATA_DIR / "bm25_corpus.json"

# =============================================================================
# Crawler behaviour
# =============================================================================

REQUEST_DELAY: Final[float] = 1.0  # seconds between page fetches
MAX_PAGES_PER_SECTION: Final[int] = 50  # safety cap per section
QC_DOCS_BASE: Final[str] = "https://www.quantconnect.com/docs/v2"

# =============================================================================
# URL Sections
#
# Keys are short identifiers used as sub-directory names under RAW_DIR.
# Values are full URLs or paths relative to QC_DOCS_BASE.
# The crawler fetches the seed page and follows all links within the same
# path prefix (up to MAX_PAGES_PER_SECTION).
#
# To add a new section:
#   1. Add an entry here as  "key": "full_url_or_relative_path"
#   2. Run: poetry run python rag/pipelines/ingest_pipeline.py --sections key
#   3. Verify: poetry run python rag/inject_context.py --query "your topic"
#
# QuantConnect doc sections (uncomment what you need):
# =============================================================================

URL_SECTIONS: dict[str, str] = {
    # -------------------------------------------------------------------------
    # Core Algorithm Development
    # -------------------------------------------------------------------------
    "indicators": f"{QC_DOCS_BASE}/writing-algorithms/indicators/supported-indicators",
    "orders": f"{QC_DOCS_BASE}/writing-algorithms/trading-and-orders/order-types",
    "lifecycle": f"{QC_DOCS_BASE}/writing-algorithms/initialization",
    "warmup": f"{QC_DOCS_BASE}/writing-algorithms/historical-data/warm-up-periods",
    "algorithm_framework": f"{QC_DOCS_BASE}/writing-algorithms/algorithm-framework",

    # -------------------------------------------------------------------------
    # Data & Securities
    # -------------------------------------------------------------------------
    "data_subscriptions": f"{QC_DOCS_BASE}/writing-algorithms/securities/asset-classes/us-equity",
    "history_requests": f"{QC_DOCS_BASE}/writing-algorithms/historical-data/history-requests",

    # -------------------------------------------------------------------------
    # Options (uncomment if your strategy trades options)
    # -------------------------------------------------------------------------
    # "options_chain": f"{QC_DOCS_BASE}/writing-algorithms/securities/asset-classes/equity-options",
    # "equity_options_universe": f"{QC_DOCS_BASE}/writing-algorithms/universes/equity-options",
    # "options_dataset": f"{QC_DOCS_BASE}/writing-algorithms/datasets/quantconnect/us-equity-option-universe",

    # -------------------------------------------------------------------------
    # Universe & Events
    # -------------------------------------------------------------------------
    # "universe_key_concepts": f"{QC_DOCS_BASE}/writing-algorithms/universes/key-concepts",
    # "scheduled_events": f"{QC_DOCS_BASE}/writing-algorithms/scheduled-events",
    # "event_handlers": f"{QC_DOCS_BASE}/writing-algorithms/key-concepts/event-handlers",

    # -------------------------------------------------------------------------
    # Backtesting & Deployment
    # -------------------------------------------------------------------------
    # "backtesting": f"{QC_DOCS_BASE}/cloud-platform/backtesting",
    # "brokerages": f"{QC_DOCS_BASE}/writing-algorithms/live-trading/brokerages",
    "live_trading": f"{QC_DOCS_BASE}/writing-algorithms/live-trading",
}
