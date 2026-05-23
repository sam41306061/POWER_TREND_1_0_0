# Handler Responsibilities

**Source:** `copilot-instructions.md`, `docs/FILE_MAP.md`
**Load when:** asked which handler owns a behavior; before implementing a new handler to avoid
overlap; before modifying routing logic in `main.py`

---

| Handler Class | File | Responsibility |
|---|---|---|
| `DynamicUniverseSelector` | `universe_filter.py` | QC coarse-filter callback: liquidity floor → top-200 by 20d $-vol → monthly cache. Force-includes QQQ. |
| `DataHandler` | `data_handler.py` | Compute + cache per `(symbol, date)`: `close`, `open`, `low`, `prior_close`, `prior_low`, `EMA21`, `SMA50`, `prior_EMA21`, `prior_SMA50`, `dollar_volume_20d` |
| `RegimeFilter` | `regime_filter.py` | Power Trend rolling-counter state machine on QQQ only; exposes `entries_allowed()` and `current_state`. |
| `EntryEngine` | `entry_engine.py` | Per-stock initial + add-on (pyramid) entry rules; gated by `regime.entries_allowed()`. |
| `PyramidingManager` | `pyramiding_manager.py` | Equal-size leg sizing; caps adds at `PYRAMID_MAX_ADDS`; tracks leg count per symbol. |
| `ExitEngine` | `exit_engine.py` | Priority-ordered per-stock exits: account DD → stop loss → SMA breakdown → EMA cross → weakness. |
| `RiskManager` | `risk_manager.py` | High-water-mark equity tracking; account drawdown gate (suspends entries + liquidates on breach). |
| `PositionManager` | `position_manager.py` | Multi-leg avg-cost position state; entry/exit P&L tracking per symbol. |

---

## Deleted Handlers (not used by Power Trend)

These files may exist on disk as templates but are not wired into the strategy:

| File | Reason Deleted |
|---|---|
| `technical_validator.py` | Options-strategy artifact — not relevant to equity trend-following |
| `setup_checker.py` | Options-strategy artifact |
| `instrument_selector.py` | Replaced by `universe_filter.py` |
| `option_analytics.py` | Power Trend is equity-only |

---

## Data Flow Summary

```
main.py (scheduled @ DAILY_EVAL_TIME)
  → DataHandler.get_indicators(symbol, today)       # cache per (symbol, date)
  → RegimeFilter.update(qqq_data)                   # QQQ only
  → if RegimeFilter.entries_allowed():
      → EntryEngine.evaluate(symbol, indicators)      # per stock in universe
          → PyramidingManager.can_add_more(leg_count)  # leg cap check
          → PyramidingManager.size_leg(price, portfolio_value)
  → ExitEngine.check_partial(trade, indicators)     # P0 stretch-trim (per open position)
  → ExitEngine.check(trade, indicators)             # P1–P4 full exit (per open position)
  → RiskManager.update(equity)                      # account-level gate
```
