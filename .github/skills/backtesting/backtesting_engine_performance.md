# Backtesting — Engine Performance

**Source**: QC Docs v2 > Cloud Platform > Backtesting > Engine Performance

---

## Overview

Monitor LEAN engine performance during backtests using CPU, memory, data throughput, and execution time metrics to optimize algorithm computational efficiency.

---

## Enabling Performance Sampling

Performance metrics are only collected when explicitly configured:

```python
# In initialize()
self.settings.performance_sample_period = timedelta(days=7)
```

---

## Performance Metrics

### Resource Usage

| Metric | Description |
|---|---|
| **CPU** | Total CPU usage percentage |
| **ManagedRAM** | RAM used on machine (managed heap) |
| **TotalRAM** | Private memory allocated (managed + unmanaged) |

### Data Throughput

| Metric | Description |
|---|---|
| **DataPoints** | Data points processed per second |
| **HistoryDataPoints** | Data points fetched from history provider |
| **ActiveSecurities** | Count of currently selected/held/open-order securities |

### Execution Time Breakdown (seconds)

| Metric | What It Measures |
|---|---|
| **Subscriptions** | Total read time for data subscriptions |
| **Selection** | Total universe selection execution time |
| **Slice** | Total time for slice creation (contains algorithm state data) |
| **Schedule** | Total scheduled event execution time |
| **Consolidators** | Total consolidator event execution time (includes indicator updates) |
| **Securities** | Total security update time (includes security change and symbol change events) |
| **Transactions** | Total order event processing time (fills, cancellations, updates, trailing stops) |
| **SplitsDividendsDelisting** | Total corporate action event time |
| **OnData** | Total `on_data()` + `alpha.update()` execution time |

---

## BOUNCE Performance Considerations

| Area | Potential Bottleneck | Mitigation |
|---|---|---|
| **Selection** | Large fundamental universe (550 symbols) | `MAX_SYMBOLS_IN_UNIVERSE` caps at 550 |
| **Consolidators** | Rainbow EMA (5 EMAs × N symbols) + ATR + ADX + Stoch per symbol | Indicator caching system (see `.github/skills/indicators/indicator_caching_rules.md`) |
| **Subscriptions** | Option contract subscriptions added dynamically | Remove subscriptions after trade close |
| **OnData** | Exit condition checks on every bar for all active trades | Max 4 concurrent positions limits overhead |
| **Transactions** | Two-phase entry (subscribe → next bar → buy) | Batched via `_pending_orders` dict |

---

## Interpreting Performance Charts

The Performance chart in backtest results shows time-series for all metrics above. Look for:

- **Rising CPU/RAM**: Memory leak or unbounded data structure growth
- **Spike in Consolidators**: Too many indicators registered; consider pruning universe
- **High Selection time**: Universe filter too complex; simplify fundamental selection
- **High OnData time**: Expensive per-bar computation; cache where possible

---

## References

- QC Docs: Cloud Platform > Backtesting > Engine Performance
- `.github/skills/indicators/indicator_caching_rules.md` — caching to reduce Consolidators time
- `.github/skills/data/data_alignment_invariants.md` — API reduction strategies
