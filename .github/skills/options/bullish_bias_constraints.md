# Bullish Bias Constraints

**Status**: Template — populate further from QC Lean v2 options docs after running ingest pipeline.

**Query to inject relevant context**:
```
python rag/inject_context.py --query "call option contract selection strike delta expiration" --top-k 5
```

---

## Trade Types

| Type | Direction | Option Right | Use Case |
|---|---|---|---|
| `BOUNCE_STANDARD` | Bullish | CALL | Price pulling back to 21 EMA in uptrend |
| `BOUNCE_200` | Bullish (slower) | CALL | Price near SMA(200) in uptrend — longer DTE justified |
| `BOUNCE_BEARISH` | Bearish | PUT | Price retracing to 21 EMA in downtrend |

---

## Bullish Call Constraints Summary

| Constraint | BOUNCE_STANDARD | BOUNCE_200 |
|---|---|---|
| Market regime | SPY > SMA(200) | SPY > SMA(200) |
| EMA structure | Rainbow up (8≥21≥34≥50≥100≥200) | Rainbow up |
| ADX | >= 20 | >= 20 |
| Stoch %K | 22–42 (pullback zone) | 22–42 |
| Pull to 21 EMA | within 2% | within 2% |
| Option min DTE | 45 | 90 |
| Option max DTE | 90 | 180 |
| Target DTE | 67 (midpoint) | 135 (midpoint) |
| Exit DTE threshold | 30 | 30 |

---

## Regime Gate (Bullish)

SPY must be above its 200-day SMA for any bullish entry:

```python
spy_price > sma200  # SPY close vs SPY SMA(200)
```

If this check fails, **no bullish entries are taken regardless of individual stock setup quality**. This is a hard gate, not a soft filter.

---

## Position Sizing for Calls

```python
position_size = account_balance * POSITION_SIZE_PCT  # 5% of account
max_spend = min(position_size, MAX_CONTRACTS * option_price * 100)
```

`MAX_CONTRACTS = 2` caps any single entry at 2 contracts regardless of account size.

---

## Notes (TODO)

> **TODO**: Fill in from QC Docs — how delta relates to extrinsic ratio, gamma risk at different DTE, theta decay profile for 45–90 DTE calls.

---

## References

- `option_contract_selector.py` — full selection logic
- `bullish_setup_checker.py` — all bullish gate checks
- `config.py` — all thresholds
- `.github/skills/options/option_chain_filtering.md` — filtering mechanics
- `.github/skills/trading/bounce_setup_validation.md` — setup validation gates
