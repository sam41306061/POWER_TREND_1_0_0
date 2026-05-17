# Silent Position Exit Failure — Post-Mortem

**Category:** bugs_and_lessons
**Discovered:** Test-2 backtest (`feat/weby_rsi_power_trend_2`), 2021–2026 period
**Severity:** Critical — defeats primary per-position risk management
**Status:** ✅ Logged / 🔧 Fix pending (`last_known_price` fallback)

---

## What Failed

JWN (Nordstrom) was entered on 2021-02-18 at avg $31.38 and held until 2025-05-21
at exit $24.66 — **4.2 years, -61% drawdown from entry**. The 7% stop loss
(`STOP_LOSS_PCT = 0.07`) should have triggered within days at $29.19.

The same failure affected ZEN (MAE -$305) and AVLR (MAE -$106), both held far
past the stop. Because no positions ever exited via stop loss, `MAX_POSITIONS_OPEN`
slots stayed permanently full from 2021-02-18, blocking all entries during every
subsequent TREND_UP window over 5 years — only 17 closed trades across the
entire backtest period.

---

## Root Cause: Two Compounding Silent Failures

### Gate A — Indicator Unavailability Bypasses Stop Loss

```
data_handler._fetch_history(symbol)
    └── LEAN raises (symbol delisted / dropped from universe)
    └── except Exception: return None          ← silent catch, no log
        └── _compute(None) → return None
            └── exit_engine.check(trade, None)
                └── if self._risk.drawdown >= MAX_ACCOUNT_DRAWDOWN_PCT:   ← only gate that still fires
                    return True, EXIT_REASON_DRAWDOWN
                └── if not indicators: return False, None                 ← CRITICAL: exits here
                    # stop loss (P2), SMA breakdown (P3), EMA cross (P4) — NEVER REACHED
```

**Affected code:**
- `handlers/data_handler.py` → `_fetch_history()` (silent `except Exception`)
- `handlers/exit_engine.py` → `check()` (early return before stop loss block)
- `main.py` → `_evaluate()` exit loop (no warning when `indicators is None` for open position)

### Gate B — Security Lookup Fails for Dropped Symbols

Even when Gate A was bypassed (account drawdown gate fired), the exit order
itself was blocked:

```
main.py._submit_exit(symbol_str, qty, reason)
    └── for security in self.securities.values():
            if str(security.symbol) == symbol_str:   ← symbol NOT found
    └── if sec is None: return                        ← silent return, no log
        # market_order never called — position never closed
```

LEAN removes delisted or universe-dropped symbols from `self.securities`.
The linear scan returns nothing. The order is silently abandoned with no log.

**Affected code:**
- `main.py` → `_submit_exit()` and `_submit_partial_exit()` (`if sec is None: return`)

---

## `last_known_price` Was Tracked But Never Used

`on_data` faithfully updates `trade.last_known_price` for every open position
as long as the security exists in `self.securities`. This price is the correct
fallback for stop-loss evaluation when `indicators is None`. It was never wired in.

```python
# on_data — updates correctly while symbol is active
for sym, trade in self._positions.active_trades.items():
    sec = self.securities.get(sym)
    if sec is not None and sec.price > 0:
        trade.last_known_price = sec.price     ← tracked

# exit_engine.check — never reads it
if not indicators:
    return False, None                          ← should fallback to last_known_price
```

---

## Cascade Effect

```
Silent exit (stop loss never fires)
  → Positions held indefinitely (avg 834 days, max 1742 days)
    → MAX_POSITIONS_OPEN = 10 slots permanently full from 2021-02-18
      → Zero new entries during all subsequent TREND_UP windows
        → 17 closed trades over 5 years (should be hundreds)
          → Sharpe 0.038 (target > 1.0)
          → PSR 2.97% (target > 60%)
          → Alpha -5.5% (underperforms SPY buy-and-hold)
          → CAGR 4.67% (target > 15%)
```

---

## Prevention Invariants (enforce in all future code)

1. **Every `if sec is None: return` in an exit path MUST log a CRITICAL message**
   before returning. A position that cannot be closed is a capital lockup.
   ```python
   if sec is None:
       self.log(f"[EXIT CRITICAL] {symbol_str}: not in securities — {qty} shares cannot be exited (reason={reason})")
       return
   ```

2. **Every `indicators is None` check for an *open position* MUST log a WARNING.**
   This is the earliest observable signal of Gate A failing.
   ```python
   if not indicators:
       self.debug(f"[EXIT WARN] {symbol}: no indicators — stop loss cannot evaluate, last_known_price={trade.last_known_price:.2f}")
   ```

3. **History fetch exceptions MUST log symbol + error before returning `None`.**
   Silent exception swallowing removes all diagnostic ability.
   ```python
   except Exception as e:
       self._algo.log(f"[DATA CRITICAL] history fetch failed for {symbol}: {e}")
       return None
   ```

4. **Any `if not indicators` guard that skips a stop-loss check MUST log.**
   The stop loss is the primary per-position risk control. Any path that bypasses
   it is a risk management failure and must be visible in the logs.

5. **`last_known_price` is the designated fallback price for stop checks.**
   When `indicators is None`, the exit engine MUST still evaluate the stop loss
   using `trade.last_known_price` rather than returning `False` unconditionally.
   ```python
   if not indicators:
       price = trade.last_known_price
       if price > 0 and trade.avg_entry_price > 0:
           if price <= trade.avg_entry_price * (1 - config.STOP_LOSS_PCT):
               return True, config.EXIT_REASON_STOP_LOSS
       return False, None
   ```

---

## Log Tags Introduced

| Tag | Level | Location | Meaning |
|---|---|---|---|
| `[DATA CRITICAL]` | `self.log()` | `data_handler._fetch_history` | LEAN history API raised an exception for a symbol |
| `[DATA WARN]` | `self.debug()` | `data_handler.get_indicators` | Insufficient bars — indicators could not be computed |
| `[EXIT WARN]` | `self.debug()` | `main._evaluate` exit loop | Open position has no indicators — stop loss blind |
| `[EXIT CRITICAL]` | `self.log()` | `main._submit_exit/partial` | Security not found in universe — order cannot be placed |
| `[EXIT SIGNAL]` | `self.debug()` | `main._evaluate` exit loop | Exit rule fired — reason and quantity visible |
| `[TRIM SIGNAL]` | `self.debug()` | `main._evaluate` exit loop | Webby RSI stretch-trim fired |
| `[ENTRY GATE]` | `self.debug()` | `main._evaluate` entry section | Regime / risk / cap gate blocked entries |
| `[ENTRY SKIP]` | `self.debug()` | `main._evaluate` entry section | Signal valid but qty=0 (insufficient cash) |
| `[REGIME TRANSITION]` | `self.debug()` | `regime_filter._transition` | State machine changed state |

---

## Related Skills

- [debugging/silent_failure_modes.md](../debugging/silent_failure_modes.md) — general silent failure catalogue
- [trading/order_management.md](../trading/order_management.md) — exit priority waterfall
- [backtesting/results_interpretation.md](../backtesting/results_interpretation.md) — Sharpe/PSR red flags
