# Performance Assessment — `handlers/`

**Date:** 2026-05-07  
**Branch:** `feat/options_selection_solution`  
**Framework:** Five Multipliers ([`.github/skills/performant_software/`](../../.github/skills/performant_software/five_multipliers.md))

---

## Phase 0 — Hot Path & Working Set

The hot path is `DataHandler.get_indicators()`, called for **up to 200 symbols** every day at 09:35.

Per-symbol work per call: `_extract()` ×5 → `_ema()` ×2 → `_atr()` ×1 → `dollar_volume_20d` computation.

**Working set estimate:**

```
~80 bars × 5 columns × 8 bytes ≈ 3.2 KB per symbol → L1 cache ✅
200 symbols total ≈ 640 KB → L2 / L3 ✅
```

The cache hierarchy is **not** the bottleneck. All performance headroom is in the compute layer.

---

## Multiplier 1 — Waste

### W1 — `_ema()`: pure Python scalar loop — 🔴 CRITICAL

**File:** `handlers/data_handler.py`

```python
for v in values[period:]:
    ema = alpha * float(v) + (1 - alpha) * ema
```

Called **twice per symbol** (today and prior EMA). At 200 symbols that is 200 × 2 × ~59 iterations = **~23,600 Python scalar multiplications per daily scan**. Every iteration pays the full CPython interpreter overhead: bytecode dispatch, type checking, heap allocation of a new float object, and reference-count updates. This is the textbook 181-instructions-per-addition problem applied to the hottest loop in the codebase.

| | Python loop | NumPy equivalent |
|---|---|---|
| Instructions per addition | ~181 | ~1 |
| Estimated relative speed | 1× | ~130–500× |

---

### W2 — `_atr()`: list-append accumulation loop

**File:** `handlers/data_handler.py`

```python
trs = []
for i in range(n - period, n):
    tr = max(hi - lo, abs(hi - prev_close), abs(lo - prev_close))
    trs.append(tr)
return sum(trs) / period
```

200 symbols × 14 iterations = **2,800 Python iterations per scan**, plus 200 list allocations. The True Range computations are fully independent of each other — no dependency chain exists — making this a missed vectorisation opportunity on top of the waste issue.

---

### W3 — `dollar_volume_20d`: `float()` coercions inside a generator

**File:** `handlers/data_handler.py`

```python
dollar_volume_20d = sum(
    float(closes[i]) * float(volumes[i]) for i in range(-dv_lookback, 0)
) / dv_lookback
```

200 × 20 = **4,000 `float()` coercions** plus negative-index arithmetic per scan. The conversion work is entirely avoidable if the underlying data is already a typed array.

---

### W4 — `_extract()`: returns plain Python lists — blocks all downstream SIMD

**File:** `handlers/data_handler.py`

```python
return [float(getattr(b, column)) for b in bars]
```

Called 5 times per symbol (opens, highs, lows, closes, volumes) = **1,000 list-building calls per scan**. Because every downstream computation (`_ema`, `_atr`, `sma_today`, `dollar_volume_20d`) operates on these plain Python lists, NumPy's SIMD path is **never triggered** anywhere in `_compute()`. This is the root cause that blocks W1, W2, and W3 from being fixed independently.

---

### W5 — `_force_include_regime()`: string allocations inside full coarse loop

**File:** `handlers/universe_filter.py`

```python
if any(str(s).split()[0].upper() == regime_str for s in symbols)
```

On every coarse refresh, this creates a new string + list split on every symbol just to check for `"QQQ"`. A pre-built set of ticker strings would reduce this to a single O(1) lookup.

---

## Multiplier 2 — IPC (Instructions Per Clock)

**Overall: ✅ / ⚠️ (partially by design)**

`_ema()` is a **serial dependency chain by algorithmic necessity** — each output is the input for the next iteration. This cannot be broken without changing the EMA definition. No action required.

`_atr()` True Range computations are **fully independent** — each `tr` does not depend on the previous `tr`. This is a missed IPC + SIMD opportunity (addressed by W2 above).

All other handlers (entry engine, exit engine, regime filter, risk manager) operate on a small dict of scalar comparisons. No IPC issues.

---

## Multiplier 3 — SIMD

**Overall: ⚠️ — flows directly from W4**

Because `_extract()` returns plain Python lists, the NumPy SIMD path is never triggered anywhere in `DataHandler._compute()`. Converting `_extract()` output to `np.ndarray(dtype=np.float64)` is the prerequisite that unblocks SIMD for:

- `sma_today` / `sma_prior` — `np.mean(closes[-50:])` vs manual `sum() / 50`
- `_atr()` True Range — `np.maximum(...)` / `np.abs(...)` vectorised across all 14 bars at once
- `dollar_volume_20d` — `np.multiply(closes, volumes).mean()` vs element-by-element generator

Note that `_ema()` remains a scalar computation even with typed arrays due to the serial dependency chain — this is the correct trade-off.

---

## Multiplier 4 — Caching

**Overall: ✅ Clean**

| Check | Status |
|---|---|
| Working set tier | L1 / L2 — no DRAM pressure |
| Memory access pattern | Sequential — index 0→N through closes |
| Dict lookups in hot path | None |
| `DataHandler._cache` design | Correct — keyed by `(str(symbol), date)`, cleared at top of scan |

No action required.

---

## Multiplier 5 — Multithreading

**Overall: N/A by design**

The 200-symbol scan is embarrassingly parallel (each symbol is independent), but the LEAN `history()` API is single-threaded and blocking. Parallelisation is not actionable without a pre-fetch architectural change. Not in scope.

---

## Priority Stack

| Priority | ID | Issue | File | Fix |
|---|---|---|---|---|
| 🔴 Critical | W1 | `_ema()` pure Python scalar loop — 23,600 interpreter ops/day | [`data_handler.py`](../handlers/data_handler.py) | NumPy EMA on typed array |
| 🟠 High | W4 | `_extract()` returns plain Python list — blocks all SIMD | [`data_handler.py`](../handlers/data_handler.py) | Return `np.ndarray(dtype=np.float64)` |
| 🟠 High | W2 | `_atr()` list-append loop — independent TRs never vectorised | [`data_handler.py`](../handlers/data_handler.py) | `np.maximum` / `np.abs` vectorised TR |
| 🟡 Medium | W3 | `dollar_volume_20d` float coercions in generator | [`data_handler.py`](../handlers/data_handler.py) | `np.multiply(closes, volumes).mean()` |
| 🟢 Low | W5 | `_force_include_regime()` string allocs per loop | [`universe_filter.py`](../handlers/universe_filter.py) | Pre-build upper-cased ticker set |

> **Note:** W4 is the prerequisite for W1, W2, and W3. They form a single coherent change to `DataHandler`.

---

## Review Summary

```
Hot path:           DataHandler.get_indicators() × 200 symbols/day
Input size:         ~80 bars × 5 cols × 8 bytes = 3.2 KB/symbol → L1 ✅

Waste (Mult 1):     ⚠️  Issues: W1 (critical), W2, W3, W4 (root cause), W5 (low)
IPC (Mult 2):       ✅  Serial EMA chain is by design; ATR is covered by W2
SIMD (Mult 3):      ⚠️  Blocked by W4 — no NumPy typed arrays in hot path
Cache (Mult 4):     ✅  L1/L2, sequential access, correct cache key design
Threading (Mult 5): N/A LEAN history() API is single-threaded

Highest-priority action: Fix _extract() → np.ndarray, then rewrite _ema / _atr / dollar_volume
Expected gain:           ~100–500× on the compute portion of the daily scan
```
