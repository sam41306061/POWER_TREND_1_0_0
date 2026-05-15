# Backtesting Deployment & Constraints

**Source:** QC Documentation — Deployment, Getting Started
**Category:** backtesting
**Status:** ✅ Populated — infrastructure limits, node specs, and deployment workflow

---

## Overview

QuantConnect backtests run on cloud servers using the open-source LEAN engine. Understanding
node specifications, resource quotas, and deployment constraints is critical for this
options-heavy strategy which processes 107 symbol option chains.

---

## Backtesting Nodes

| Model | vCPU | Speed (GHz) | RAM (GB) | GPU |
|---|---|---|---|---|
| **B-MICRO** | 2 | 3.3 | 8 | 0 |
| B2-8 | 2 | 4.9 | 8 | 0 |
| B4-12 | 4 | 4.9 | 12 | 0 |
| B4-16-GPU | 4 | 3.0 | 16 | 1/3 |
| B8-16 | 8 | 4.9 | 16 | 0 |

**Current environment:** Community tier with B-MICRO node (2 vCPU, 8 GB RAM).

### RAM Considerations for This Strategy

- Each option chain subscription consumes memory for contract data
- 107 symbols × option chain = significant memory footprint
- IV computation (`_populate_iv_data()`) holds intermediate results in memory
- B-MICRO (8 GB) may hit limits with full universe — monitor ManagedRAM in Performance chart
- If OOM occurs, consider reducing universe size or upgrading to B4-12 (12 GB)

### Free Tier Restrictions

- 20-second delay when launching backtests
- 200 backtests per day cap
- These restrictions are lifted on paid tiers

---

## Resource Quotas by Tier

### Log Limits

| Tier | Per Backtest | Per Day |
|---|---|---|
| Free | 10 KB | 3 MB |
| Quant Researcher | 100 KB | 3 MB |
| Team | 1 MB | 10 MB |
| Trading Firm | 5 MB | 50 MB |
| Institution | Unlimited | Unlimited |

**Impact on this strategy:** With 107 symbols scanned daily, verbose logging fills 10 KB
quickly. Use conditional logging (log only when gates pass/fail for candidates with
earnings) to stay within quota. Check remaining log storage: Organization → Resources.

### Order Limits

| Tier | Max Orders per Backtest |
|---|---|
| Free | 10,000 |
| Quant Researcher | 10,000,000 |
| Team+ | Unlimited |

With `FIXED_CONTRACTS = 10` and `MAX_POSITIONS_OPEN = 10`, this strategy generates relatively
few orders. The 10K free-tier limit is unlikely to be hit.

### Chart Quotas

| Tier | Max Series | Max Points per Series |
|---|---|---|
| Free | 10 | 4,000 |
| Quant Researcher | 10 | 8,000 |
| Team | 25 | 16,000 |

Custom charts (IV tracking, delta tracking) count against these limits. If exceeded,
algorithm execution stops with "Exceeded maximum chart series count."

---

## Runtime Quota

- **Maximum runtime:** 12 hours per backtest
- Runtime depends on data volume, algorithm complexity, and node type
- This strategy's IV convergence solver was previously hitting this limit (>720 min)
  before the fix to whitelist only candidates with earnings dates
- Monitor via Performance chart's CPU and OnData series

---

## Deployment Workflow

### Build & Run

1. Open project in QC IDE
2. Click Build icon — compiler checks for errors, highlights failures in red
3. Click Backtest icon — "Received backtest backtestName request" confirms launch
4. Results page opens in new tab, updates in real-time
5. Closing/refreshing IDE does not interrupt the backtest (runs on cloud servers)

### Stopping a Backtest

- Resources panel → click stop icon next to backtest node
- Requires stop node permissions for nodes used by other members

### Concurrent Backtesting

| Tier | Max Concurrent Backtests |
|---|---|
| Free | 1 |
| Quant Researcher | 2 |
| Team | 10 |
| Trading Firm+ | Unlimited |

Need multiple backtesting nodes for concurrent execution. For parameter exploration,
use QC Optimization instead of manual concurrent backtests.

---

## Backtest Management

- **Rename:** Hover over backtest → pencil icon → enter name → OK
  - Or programmatically: `self.set_name("Backtest Name")`
- **Clone:** Hover → clone icon → creates new project with backtest code
- **Delete:** Hover → trash can icon → removes backtest permanently
- **Share:** Results page → Share Results → Make Public → copy URL or embed code
- **Backtest ID:** First line of log file (e.g. `8b16cec0c44f75188d82f9eadb310e17`)

---

## Security

- Code stored in database, isolated from internet
- Compiled and obfuscated before cloud deployment
- SSH key login, nightly security patches
- Only a handful of internal employees have database access

---

## Invariants

1. **B-MICRO 8 GB RAM is the binding constraint** — option chain memory usage must be
   monitored; the IV convergence fix (whitelisting only candidates with earnings) was
   critical to staying within this limit
2. **12-hour runtime cap** — if backtest approaches this, the IV solver or data pipeline
   needs optimization; current fix reduced runtime from >720 min to acceptable range
3. **10 KB log limit on free tier** — use `self.debug()` for development, remove verbose
   logging before production backtests; prefer structured log messages
4. **Backtest results archived after 12 months of inactivity** — download important results
5. **If backtest produces > 700 MB of output data, results page appears empty** — reduce
   charting or logging
