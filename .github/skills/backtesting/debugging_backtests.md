# Debugging Backtests

**Source:** QC Documentation — Debugging, `handlers/`, `main.py`
**Category:** backtesting
**Status:** ✅ Populated — debugger workflow, logging strategy, and common diagnosis patterns

---

## Overview

QuantConnect provides a built-in debugger for backtesting that supports breakpoints,
step-through execution, variable inspection, and watch expressions. Combined with
strategic logging, this is the primary toolset for diagnosing why the algorithm
behaves unexpectedly during backtests.

---

## Debugger Workflow

### Setup

1. Open project in QC IDE
2. Click to the left of a line number to add a breakpoint (red dot appears)
3. Click the Debug icon to launch debugger
4. Run and Debug panel opens when first breakpoint is hit

### Breakpoint Types

| Type | How to Set | Use Case |
|---|---|---|
| **Standard** | Click left of line number | Pause at specific code line |
| **Conditional (Expression)** | Right-click → Edit Breakpoint → Expression | Pause only when condition is true |
| **Conditional (Hit Count)** | Right-click → Edit Breakpoint → Hit Count | Pause after N hits |

### Useful Conditional Breakpoints for This Strategy

```python
# Break only when a specific symbol passes Phase 1
str(symbol) == "AAPL"

# Break when earnings are within entry window
days_to_earnings is not None and 7 <= days_to_earnings <= 30

# Break when IV is elevated
iv_ratio > 1.5

# Break on position entry
len(self._active_positions) > 0
```

### Debugger Controls

| Button | Shortcut | Action |
|---|---|---|
| Continue | — | Run to next breakpoint |
| Step Over | Alt+F10 | Execute current line, move to next |
| Step Into | Alt+F11 | Enter function definition on current line |
| Restart | Shift+F11 | Restart entire debugger session |
| Disconnect | Shift+F5 | Exit debugger |

---

## Variable Inspection

### Local Variables Panel

The Variables section shows all local variables at the current breakpoint:

- Click object variables to expand and see member values
- Right-click a variable → Set Value to modify during execution
- Panel updates as algorithm executes

### Watch Expressions

Add custom expressions to the Watch section to monitor specific values:

```python
# Useful watch expressions for this strategy:
self.time.date()                           # Current algorithm date
len(self._candidates_with_earnings)        # Number of active candidates
len(self._active_positions)                # Current position count
self.portfolio.total_portfolio_value       # Current equity
str(symbol)                                # Current symbol being processed
```

### DataFrames in Debugger

If inspecting a DataFrame variable (e.g., history data), the debugger renders it
in table format for readability.

---

## Logging Strategy

### QC Logging Methods

| Method | Purpose | Visibility |
|---|---|---|
| `self.log(msg)` | General log | Logs tab (counts against quota) |
| `self.debug(msg)` | Debug-level log | Logs tab (counts against quota) |
| `self.error(msg)` | Error-level log | Logs tab + highlighted |

### Log Quota Awareness

Free tier: 10 KB per backtest, 3 MB per day. With 107 symbols scanned daily:

```python
# BAD — logs for all 107 symbols every day
for symbol in self._universe:
    self.log(f"Scanning {symbol}")

# GOOD — log only actionable events
if result["valid"]:
    self.log(f"PASS: {symbol} — {days_to_earnings}d to earnings")
```

### Structured Log Format for This Strategy

```python
# Gate-level logging (only for candidates that reach Phase 1)
self.log(f"[SCAN] {symbol}: earnings={days_to_earnings}d, "
         f"regime={'OK' if regime_ok else 'FAIL'}, "
         f"technicals={'OK' if tech_pass else 'FAIL'}, "
         f"iv_elevated={iv_elevated}")

# Entry logging
self.log(f"[ENTRY] {symbol}: {contracts}x {option_symbol} @ ${price:.2f}, "
         f"delta={delta:.3f}, iv={iv:.1%}")

# Exit logging
self.log(f"[EXIT] {symbol}: reason={exit_reason}, pnl=${pnl:.2f}, "
         f"held={holding_days}d")
```

---

## Common Diagnosis Patterns

### "Algorithm didn't trade"

1. Check logs for gate failures — which gate is blocking?
2. Set breakpoint in `_scan_universe()` at the `validate_setup()` call
3. Inspect `result["details"]` dict to see which boolean is `False`
4. Cross-reference with [why_didnt_my_algo_trade.md](../debugging/why_didnt_my_algo_trade.md)

### "Backtest timed out (>12 hours)"

1. Enable Performance chart: `self.settings.performance_sample_period = timedelta(7)`
2. Check OnData and Slice timing — are they dominating?
3. Verify `_populate_iv_data()` is whitelisting only candidates with earnings
4. Check ActiveSecurities count — should match expected chains, not all 107

### "Results page is empty"

- Backtest generated > 700 MB of output data
- Reduce custom chart series or remove verbose per-symbol logging
- Check chart quotas: Free tier = 10 series × 4,000 points max

### "Unexpected entries/exits"

1. Download Orders CSV → check timestamps and fill prices
2. Use Asset Plot: Orders tab → click chart icon next to symbol
3. Hover over order annotations to see tags
4. Set breakpoints in `_check_entry_triggers()` and `_process_exits()`

### "Memory error / OOM"

1. Check ManagedRAM in Performance chart
2. Verify `data_handler.clear_cache()` is called between daily scans
3. Check option chain count — should match universe size, not grow unbounded
4. Consider upgrading from B-MICRO (8 GB) to B4-12 (12 GB)

---

## Filtering and Downloading Logs

- **Filter:** Logs tab → enter search string in "Filter logs" field
- **Download:** Logs tab → Download Logs button
- **Programmatic access:** Use `read_backtest_orders()` in Research Environment
- **Timestamps:** Log timestamps use algorithm time zone; CSV downloads use UTC

---

## Invariants

1. **At least one breakpoint required** to launch the debugger
2. **Debugger runs on cloud** — closing IDE does not terminate debug session
3. **Log budget: ~100 characters × 100 events = 10 KB** — plan log density accordingly
4. **Order tags are the best debugging tool** — add descriptive tags to every order to
   explain why it was placed (e.g., `f"Phase2-pass delta={delta:.2f}"`)
5. **Use conditional breakpoints to avoid stepping through 107 symbols** — filter to
   specific symbols or conditions of interest
