# RAG Pipeline — <!-- TODO: Project Name -->

AI-facing knowledge layer for your LEAN algorithm. Crawls QuantConnect documentation,
indexes it with BM25, and surfaces the most relevant API reference directly into
GitHub Copilot context via `docs/RAG_CONTEXT.md`.

**No external services required** — pure Python, no embeddings, no GPU, no vector DB.

---

## How It Works

```
QC Docs (public)
    │
    │  playwright_crawler.py  (headless browser, follows in-section links)
    ▼
rag/data/raw/<section>/          ← raw HTML files (gitignored)
    │
    │  html_cleaner.py           (strip nav, ads, scripts)
    │  markdown_converter.py     (markdownify, keep code blocks + headers)
    │  chunker.py                (header-aligned 200–500 token chunks)
    │  metadata_extractor.py     (URL, section_path, crawl_date)
    ▼
rag/data/doc_store.json          ← all chunks + metadata (gitignored)
    │
    │  bm25_store.py             (rank_bm25.BM25Okapi, save/load tokenized corpus)
    ▼
rag/data/bm25_corpus.json        ← pre-tokenized index (gitignored)
    │
    │  inject_context.py         (CLI: --query "..." --top-k N)
    ▼
docs/RAG_CONTEXT.md              ← Copilot reads this as workspace context
```

---

## Prerequisites

### 1. Install RAG dependencies

```bash
poetry install --with rag
```

This installs the optional `rag` dependency group (Playwright, markdownify, rank-bm25,
BeautifulSoup4, lxml). The core strategy dependencies are unaffected.

### 2. Install Playwright browsers

```bash
poetry run playwright install chromium
```

This downloads the Chromium binary used for JS-rendered page crawling. Only needed once.
Re-run if Playwright is upgraded.

---

## Quickstart

### Ingest one section

```bash
# Ingest a specific section
poetry run python rag/pipelines/ingest_pipeline.py --sections indicators

# Ingest multiple sections
poetry run python rag/pipelines/ingest_pipeline.py --sections indicators lifecycle

# Ingest all enabled sections (takes ~10–20 minutes due to rate limiting)
poetry run python rag/pipelines/ingest_pipeline.py
```

### Query the corpus

```bash
# Write top-5 results for a query to docs/RAG_CONTEXT.md
poetry run python rag/inject_context.py --query "option chain filtering delta"

# Use top-3, print to stdout instead of writing file
poetry run python rag/inject_context.py --query "EMA warmup history" --top-k 3 --stdout

# Custom output path
poetry run python rag/inject_context.py --query "market order placement" --output my_context.md
```

### Typical development session

```bash
# Before working on indicator logic:
poetry run python rag/inject_context.py --query "EMA SMA warm-up indicator IsReady"

# Before working on order placement:
poetry run python rag/inject_context.py --query "market order buy option fill"

# Before working on scheduling:
poetry run python rag/inject_context.py --query "schedule scheduled events daily"
```

Copilot will automatically read `docs/RAG_CONTEXT.md` as workspace context and use the
retrieved QC API reference in its suggestions.

---

## Available Sections

Defined in `rag/crawler/config.py` → `URL_SECTIONS`. Enable sections relevant to your
strategy by uncommenting them in that file.

| Key | QC Docs Path | What it covers |
|---|---|---|
| `indicators` | `/writing-algorithms/indicators/supported-indicators` | SMA, EMA, ATR, all built-in indicators |
| `orders` | `/writing-algorithms/trading-and-orders/order-types` | Market/Limit/Stop orders, fills |
| `data_subscriptions` | `/writing-algorithms/securities/asset-classes/us-equity` | Equity data, history API |
| `lifecycle` | `/writing-algorithms/initialization` | initialize(), scheduling, set_warm_up |
| `warmup` | `/writing-algorithms/historical-data/warm-up-periods` | Warm-up periods, IsWarmingUp |

<!-- Uncomment in rag/crawler/config.py as needed: -->
<!-- | `options_chain` | `/writing-algorithms/securities/asset-classes/equity-options` | Option chains, contracts, Greeks | -->
<!-- | `algorithm_framework` | `/writing-algorithms/algorithm-framework` | Alpha, execution, portfolio construction | -->
<!-- | `brokerages` | `/writing-algorithms/live-trading/brokerages` | Brokerage-specific notes | -->

---

## Adding New QC Doc URLs

### Step 1 — Add the URL to `rag/crawler/config.py`

```python
URL_SECTIONS: Final[dict] = {
    # ... existing entries ...
    "my_new_section": "/writing-algorithms/path/to/new/section",
}
```

The key becomes the subdirectory name under `rag/data/raw/` and the label in
`docs/RAG_CONTEXT.md`. Use lowercase with underscores.

### Step 2 — Run the ingest pipeline

```bash
poetry run python rag/pipelines/ingest_pipeline.py --sections my_new_section
```

### Step 3 — Verify with a test query

```bash
poetry run python rag/inject_context.py --query "your topic keywords" --top-k 3 --stdout
```

If results are poor:
- Try different query keywords (BM25 is keyword-based — exact terms matter)
- Check `rag/data/raw/my_new_section/` to confirm HTML was saved
- Inspect a raw file to verify the DOM selector in `html_cleaner.py` extracts content

---

## Re-Crawling Existing Sections

By default, the pipeline skips pages already crawled **today**. To force a full refresh:

```bash
poetry run python rag/pipelines/ingest_pipeline.py --sections indicators --force
```

Use `--force` when QC docs have been updated or you want to capture new pages.

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `ModuleNotFoundError: playwright` | Run `poetry install --with rag` |
| Playwright browser not found | Run `poetry run playwright install chromium` |
| Empty corpus after ingest | Check `rag/data/raw/` for HTML files; verify URL paths |
| Poor query results | Use exact keywords that appear in QC docs; try synonyms |
| Stale data | Re-run with `--force` flag |
