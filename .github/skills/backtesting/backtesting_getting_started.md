# Backtesting — Getting Started

**Source**: QC Docs v2 > Cloud Platform > Backtesting > Getting Started

---

## Overview

Execute backtests, rename result files, configure out-of-sample periods to prevent overfitting, view backtest history, obtain backtest IDs, and share results via public URLs or embedded widgets.

---

## Key Rules & Invariants

- Backtest names are auto-generated arbitrarily (e.g., "Smooth Apricot Chicken")
- Use `self.set_name("My Custom Backtest Name")` to rename programmatically
- Backtest ID appears in the **first line of the log file** (format: `8b16cec0c44f75188d82f9eadb310e17`)
- Out-of-sample period prevents teams from using recent data during development
- Only organization admins can change the out-of-sample period (via organization homepage settings)
- Shared backtests require explicit "Make Public" action → generates shareable URL and iframe embed code
- "Make Private" reverts visibility but the backtest record persists

---

## Programmatic Backtest Naming

```python
# In initialize() or anywhere during algorithm execution
self.set_name("My Custom Backtest Name")
```

---

## Out-of-Sample Period

The out-of-sample period reserves recent data to validate strategy performance on unseen data. Backtests run only until the start of this hold-out period.

**Configuration**: Organization homepage → Settings (admin only)

---

## Sharing Results

1. Open backtest results
2. Click "Make Public"
3. Copy the generated URL or iframe embed code
4. "Make Private" to revoke access

---

## References

- QC Docs: Cloud Platform > Backtesting > Getting Started
- `.github/skills/backtesting/backtesting_deployment_quotas.md` — quota limits
