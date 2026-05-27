# Config Thresholds

**Source:** `config.py`
**Load when:** implementing handlers, writing tests, or verifying strategy parameters

All strategy thresholds are `Final` typed constants in `config.py`. Never hardcode these values
in handlers or tests — always import by name.

---

| Parameter | Value | Constant | Handler(s) |
|---|---|---|---|
| Regime symbol | QQQ | `REGIME_SYMBOL` | `regime_filter.py` |
| Regime EMA period | 21 | `REGIME_EMA_PERIOD` | `regime_filter.py`, `data_handler.py` |
| Regime SMA period | 50 | `REGIME_SMA_PERIOD` | `regime_filter.py`, `data_handler.py` |
| Power Trend activation — low above EMA | 10 days | `LOW_ABOVE_EMA_DAYS` | `regime_filter.py` |
| Power Trend activation — EMA above SMA | 5 days | `EMA_ABOVE_SMA_DAYS` | `regime_filter.py` |
| Universe size | Top 450 stocks | `UNIVERSE_TOP_N` | `universe_filter.py` |
| Universe refresh cadence | 14 days | `UNIVERSE_REFRESH_DAYS` | `universe_filter.py` |
| Liquidity floor — price | ≥ $20 | `MIN_PRICE` | `universe_filter.py` |
| Liquidity floor — 20d $-volume | ≥ $50M | `MIN_DOLLAR_VOLUME` | `universe_filter.py` |
| Pyramid cap | 3 adds | `PYRAMID_MAX_ADDS` | `entry_engine.py`, `pyramiding_manager.py` |
| Per-leg sizing | 2% of portfolio | `INITIAL_LEG_SIZE_PCT` | `pyramiding_manager.py` |
| Max open positions | 10 | `MAX_POSITIONS_OPEN` | `entry_engine.py` |
| Stop loss (per position) | 7% | `STOP_LOSS_PCT` | `exit_engine.py` |
| Account drawdown gate | 15% | `MAX_ACCOUNT_DRAWDOWN_PCT` | `risk_manager.py` |
| Daily evaluation time | 09:35 ET | `DAILY_EVAL_TIME` | `main.py` scheduled event |
