# Option Chain Filtering — Power Trend Long-Dated Calls

**Source:** [handlers/instrument_selector.py](../../../handlers/instrument_selector.py), [main.py](../../../main.py) (`_ensure_option_subscription`, `_process_pending_entries`)
**Category:** options
**Invariant level:** MUST — tests enforce these rules

---

## Overview

`InstrumentSelector` picks one long-dated call contract from a chain. `main.py` lazily
subscribes to a per-underlying option universe on the first signal, then `on_data` reads
the chain and runs the selector. There is **no** IV gate, earnings logic, or option
analytics handler — just contract picking and DTE/premium/regime exits.

---

## Contract Selection Pipeline

```
chain (OptionChain | iterable[OptionContract])
    │
    ├── 1. Right == "Call" / "C" (case-insensitive)
    ├── 2. DTE in [OPTION_DTE_MIN, OPTION_DTE_MAX]            (90 .. 270)
    ├── 3. abs(delta) in [OPTION_DELTA_MIN, OPTION_DELTA_MAX] (0.70 .. 0.95)
    ├── 4. OpenInterest >= OPTION_MIN_OPEN_INTEREST           (100)
    ├── 5. (ask - bid) / mid <= OPTION_MAX_BID_ASK_SPREAD_PCT (0.10) when both quotes > 0
    │
    └── Rank: (abs(delta - 0.70), abs(dte - 180), spread)
            → ContractRecord
```

A `ContractRecord` carries:
`contract_symbol, underlying_symbol, expiry, strike, delta, bid, ask, mid_price, open_interest`.

---

## Config Constants

| Constant | Value | Purpose |
|---|---|---|
| `OPTION_DTE_MIN` | 90 | Lower DTE bound |
| `OPTION_DTE_MAX` | 270 | Upper DTE bound |
| `OPTION_TARGET_DELTA` | 0.70 | Selection target |
| `OPTION_DELTA_MIN` | 0.70 | Lower delta band |
| `OPTION_DELTA_MAX` | 0.95 | Upper delta band (excludes ~delta-1) |
| `OPTION_MIN_OPEN_INTEREST` | 100 | Liquidity floor |
| `OPTION_MAX_BID_ASK_SPREAD_PCT` | 0.10 | Quoted-spread sanity |
| `OPTION_PREMIUM_LEG_BUDGET_PCT` | 0.05 | Per-leg premium budget (sizing) |
| `OPTION_PREMIUM_STOP_LOSS_PCT` | 0.50 | Per-leg premium stop |
| `OPTION_FORCE_EXIT_DAYS_BEFORE_EXPIRY` | 14 | DTE force-close threshold |
| `OPTION_CONTRACT_MULTIPLIER` | 100 | Shares per contract |

---

## Delta Extraction Order

1. `contract.Greeks.Delta` (LEAN production)
2. `contract.greeks.delta` (LEAN OptionUniverse / lower-case)
3. `contract.delta` (test stub attribute)
- Returns `abs()` so put-style negative deltas are normalized.

## Open Interest Extraction Order

1. `contract.OpenInterest`
2. `contract.open_interest`
- Coerced to `int`; missing → `0` → fails the gate.

---

## Lazy Subscription Lifecycle (`main.py`)

`main.py` does not blanket-subscribe option chains for the entire 200-symbol universe. It
subscribes lazily on the first signal for an underlying and unsubscribes when the
underlying leaves the universe with no open trade.

```python
# initialize()
self.universe_settings.data_normalization_mode = DataNormalizationMode.RAW

# _ensure_option_subscription(underlying)  — called from _evaluate() on signal
option = self.add_option(underlying, Resolution.DAILY)
option.set_filter(
    lambda u: u.calls_only()
              .expiration(OPTION_DTE_MIN, OPTION_DTE_MAX)
              .delta(OPTION_DELTA_MIN, OPTION_DELTA_MAX)
)
self._subscribed_options[str(underlying)] = option.symbol

# on_securities_changed(changes)
for sec in changes.removed_securities:
    if str(sec.symbol) in self._positions.active_trades:
        continue                             # keep chain while a trade is open
    self.remove_security(self._subscribed_options.pop(str(sec.symbol)))
```

### Pending-entry queue

Because LEAN populates the chain on the next bar after `add_option()`, signals are queued
and resolved inside `on_data`:

```python
self._pending_entries.append(
    {"underlying_str": ..., "signal": ..., "queued_date": today, ...}
)

# on_data(slice)  →  _process_pending_entries(slice)
chain = slice.option_chains.get(self._subscribed_options[sym_str])
record = self._selector.select(sym_str, chain, today=self.time.date())
contracts = self._pyramiding.size_leg(record.mid_price, self.portfolio.cash)
self.market_order(record.contract_symbol, contracts)
```

A queued entry that is not resolved within 5 calendar days is dropped.

### Required: RAW data normalization

`DataNormalizationMode.RAW` is mandatory — strike prices are absolute, so the underlying
must report unadjusted prices to remain comparable.

```python
self.universe_settings.data_normalization_mode = DataNormalizationMode.RAW
```

---

## Sizing — Premium Budget per Leg

```
contracts = floor(OPTION_PREMIUM_LEG_BUDGET_PCT * cash_value /
                  (mid_premium * OPTION_CONTRACT_MULTIPLIER))
```

- `cash_value` is `algorithm.portfolio.cash` (CURRENT free cash, not total value).
- Each leg's order shrinks cash, organically tapering the next pyramid add.
- Pyramid cap: `1 + PYRAMID_MAX_ADDS` legs total.

---

## Exit Rules (option-aware)

`ExitEngine.check(trade, indicators, today, premium_lookup)` returns
`list[(leg_or_None, reason)]`:

| Priority | Reason | Scope | Trigger |
|---|---|---|---|
| 1 | `ACCOUNT_DRAWDOWN` | Trade-wide | `risk.drawdown >= MAX_ACCOUNT_DRAWDOWN_PCT` |
| 2 | `SMA_BREAKDOWN` | Trade-wide | `underlying close < SMA50` |
| 3 | `EMA_CROSS` | Trade-wide | `EMA21 < SMA50` |
| 4 | `DTE_FORCE_CLOSE` | Per leg | `(leg.expiry - today).days <= 14` |
| 5 | `PREMIUM_STOP_LOSS` | Per leg | `premium_lookup(c) <= leg.fill_price * 0.50` |

Trade-wide rules short-circuit and return a single `(None, reason)`. Per-leg rules can
return multiple decisions; sibling legs on longer-dated contracts remain open after a
single-leg DTE or premium exit.

`premium_lookup` is injected from `main.py` (`_option_mid`) so the engine stays
LEAN-free.

---

## NOT in scope

- IV gates / IV history tracking (deleted with `OptionAnalytics`)
- Earnings calendar logic
- Theta or vega monitoring
- Rolling contracts forward
- Spreads, puts, short options
