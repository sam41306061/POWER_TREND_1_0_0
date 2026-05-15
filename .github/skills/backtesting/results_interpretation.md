# Backtesting Results Interpretation

**Source:** QC Documentation — Backtesting Results & Report, `config.py`
**Category:** backtesting
**Status:** ✅ Populated — key metrics and thresholds for evaluating this strategy

---

## Overview

After deploying a backtest on QuantConnect, the results page displays runtime statistics,
built-in charts, key statistics, orders, trades, and logs. This skill defines which
metrics matter most for an earnings-based options strategy and how to interpret them.

---

## Runtime Statistics Banner

The top banner shows live-updating statistics during execution:

| Statistic | What It Means for This Strategy |
|---|---|
| **Equity** | Total portfolio value. Should grow steadily with controlled drawdowns. |
| **Fees** | Total transaction costs. Options commissions are significant — monitor fee drag. |
| **Holdings** | Absolute value of all positions. With `FIXED_CONTRACTS = 10`, max ~10 positions × 10 contracts. |
| **Net Profit** | Dollar P&L. Must account for fees + slippage on option spreads. |
| **PSR** | Probability that estimated Sharpe > benchmark. Target PSR > 0.5 for statistical significance. |
| **Return** | Percentage return. Compare to SPY benchmark over same period. |
| **Unrealized** | Profit if all positions liquidated now. High unrealized relative to equity = concentration risk. |

---

## Key Overall Statistics

The Overview tab shows Overall Statistics and Rolling Statistics tables. Critical metrics:

### Primary Metrics

| Metric | Healthy Range | Red Flag |
|---|---|---|
| **Sharpe Ratio** | > 1.0 | < 0.5 indicates poor risk-adjusted returns |
| **PSR (Probabilistic Sharpe)** | > 60% | < 50% means Sharpe estimate is unreliable |
| **Drawdown** | < 20% | > 30% suggests insufficient position sizing or exit discipline |
| **Win Rate** | > 55% | < 45% for directional options strategy suggests thesis failure |
| **Profit-Loss Ratio** | > 1.5 | < 1.0 means average losses exceed average wins |
| **Compounding Annual Return** | > 15% | Negative CAGR over full cycle = strategy not viable |

### Secondary Metrics

| Metric | Relevance |
|---|---|
| **Alpha** | Excess return vs benchmark — positive alpha confirms earnings edge |
| **Beta** | Market correlation — this strategy should have moderate beta (0.3–0.7) due to call bias |
| **Total Trades** | With `MAX_POSITIONS_OPEN = 10` and 107-symbol universe, expect moderate trade count |
| **Total Fees** | Options fees compound — if fees > 10% of gross profit, consider contract sizing |
| **Estimated Strategy Capacity** | Maximum capital before market impact — options strategies typically have lower capacity |
| **Information Ratio** | Excess return per unit of tracking error — higher is better |
| **Treynor Ratio** | Return per unit of systematic risk — useful for comparing to other directional strategies |

---

## Built-In Charts

| Chart | What to Look For |
|---|---|
| **Strategy Equity** | Smooth upward curve with shallow drawdowns. Staircase pattern = earnings-driven returns. |
| **Drawdown** | Underwater periods should recover within 1–2 earnings cycles. Prolonged drawdown = regime mismatch. |
| **Exposure** | Long-only exposure from calls. Spikes = multiple concurrent positions near earnings. |
| **Portfolio Turnover** | Should spike around earnings clusters (Jan/Apr/Jul/Oct) when many positions open/close. |
| **Assets Sales Volume** | Should show diversification across symbols, not concentration in 1–2 names. |

---

## Custom Chart Types

| Type | Use Case |
|---|---|
| `LINE` | Time series data |
| `SCATTER` | Correlation / distribution plots |
| `CANDLE` | OHLC price data |
| `BAR` | Discrete period comparisons |
| `FLAG` | Event markers |
| `STACKED_AREA` | Proportional composition over time |
| `PIE` | Single-point composition |
| `TREEMAP` | Hierarchical proportions |
| `HEATMAP` | 2D density / correlation matrix |
| `SCATTER_3D` | Three-variable relationships |

**Marker symbols**: `NONE`, `CIRCLE`, `SQUARE`, `DIAMOND`, `TRIANGLE`, `TRIANGLE_DOWN`

---

## Performance Chart (Code Optimization)

Enable with `self.settings.performance_sample_period = timedelta(7)` to monitor:

| Series | Concern for This Strategy |
|---|---|
| **CPU** | IV computation is CPU-intensive — watch for spikes during `_populate_iv_data()` |
| **ManagedRAM** | 107-symbol option chains consume memory — monitor for OOM on B-MICRO (8GB) |
| **ActiveSecurities** | Should equal number of symbols with active option chains |
| **DataPoints** | High data point rate from option chain subscriptions |
| **OnData** | If OnData time dominates, optimize the option chain filtering pipeline |

---

## Backtest Report

Generate via Results → Report tab → Download Report. Contains:

- **Returns per Trade** — histogram showing distribution; healthy strategy shows right-skewed distribution
- **Daily Returns** — blue (profitable) / gray (unprofitable) bars; expect clusters around earnings dates
- **Monthly Returns** — heatmap; Jan/Apr/Jul/Oct should show stronger green (earnings season months)
- **Annual Returns** — bar chart; red dotted line = average annual return
- **Cumulative Returns** — blue line (algo) vs gray line (benchmark); algo should outperform over full cycle
- **Drawdown** — top 5 drawdown periods highlighted; worst drawdowns should be market-wide events
- **Rolling Beta** — 6-month and 12-month trailing; monitor for unintended market correlation
- **Rolling Sharpe** — 6-month and 12-month trailing; should remain positive across most periods
- **Crisis Events** — performance during DotCom, GFC, COVID, etc.; earnings strategy may suffer in panics

---

## Orders & Trades Analysis

- **Orders tab** → click Asset Plot icon to see price chart with order annotations
- **Trades tab** → shows closed trades with P&L per trade
- Download Orders CSV for offline analysis (timestamps in UTC)
- Access programmatically: `read_backtest_orders()` in Research Environment

### Asset Plot Annotations

| Symbol | Meaning |
|---|---|
| Gray circle | Order submission |
| Blue marker | Order update |
| Gray square | Order cancellation |
| Green arrow | Buy fill |
| Red arrow | Sell fill |

- Hover to see price and order tag
- Period buttons: 1m, 3m, 1y, All
- Drag to zoom any time range
- Fill prices shown at actual fill level (may differ from asset price due to slippage/fill models)
- Use order tags to track which gate triggered exits

---

## Invariants

1. **Always compare to SPY benchmark** — the strategy must generate alpha above buy-and-hold SPY
2. **Fee drag check** — if `Total Fees / abs(Net Profit) > 0.20`, fees are eroding too much return
3. **Trade count sanity** — with 107-symbol universe over 1 year, expect 50–200 trades depending on
   how many pass all 6 gates
4. **Drawdown recovery** — max drawdown should recover within 60 trading days; longer = regime issue
5. **If backtest produces > 700 MB data, results page appears empty** — reduce logging or chart data
