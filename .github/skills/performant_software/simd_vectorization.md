# SIMD — Multiplier 3: Single Instruction, Multiple Data

**Source:** Computer Enhance Course — Prologue  
**See also:** [five_multipliers.md](five_multipliers.md), [ipc_dependency_chains.md](ipc_dependency_chains.md)

---

## Core Principle

**SIMD** = one instruction that operates on multiple data values simultaneously.

Where a regular 32-bit integer add processes one pair of numbers, a SIMD add processes 4, 8, or 16 pairs — in one instruction, with one decode, and one scheduling slot.

SIMD returns to lever 1 (reducing total instructions) after IPC has addressed lever 2 (instruction efficiency). The insight is that most runtime is spent in loops that do the same small set of operations over large arrays — SIMD bakes that repetition into the hardware.

---

## How SIMD Works: Lanes

SIMD instructions operate on **packed** registers. Each sub-slot is a **lane**. Lanes always pair directly — lane 0 adds to lane 0, lane 1 to lane 1, etc. They never mix unless a special cross-lane instruction is used.

| Instruction set | Register width | Lanes (32-bit int) | Lanes (16-bit) | Lanes (8-bit) |
|---|---|---|---|---|
| SSE / SSSE3 | 128-bit | 4 | 8 | 16 |
| AVX / AVX2 | 256-bit | 8 | 16 | 32 |
| AVX-512 | 512-bit | 16 | 32 | 64 |

> **Key insight:** smaller element widths pack more lanes into the same register. If your data fits in 16-bit or 8-bit values, you get proportionally more work per instruction. Choosing the smallest dtype that holds your numeric range is itself a SIMD optimization.

---

## Why SIMD Improves Performance

A natural question: if one `paddd` does four adds, but the CPU still does the same arithmetic, where is the savings?

The savings is in the **CPU front end**. Before any instruction executes, the CPU must:
1. Decode it
2. Identify its inputs
3. Check for dependencies
4. Schedule it for an execution unit

This decode-and-schedule work has a real per-instruction cost. SIMD reduces it proportionally: one `paddd` (doing 4 adds) costs the same front-end slot as one `add` (doing 1 add). Four useful additions for the price of one decode.

---

## SIMD + IPC Combined

A single SIMD accumulator still creates a serial dependency chain — each SIMD add reads the output of the previous SIMD add. The fix is identical to the IPC fix: **multiple independent SIMD accumulators**.

| Strategy | Width | Accumulators | Adds / cycle |
|---|---|---|---|
| Scalar, 1 accumulator | scalar | 1 | 0.99 |
| AVX, 1 accumulator | 256-bit | 1 | 7.0 |
| AVX, 2 accumulators | 256-bit | 2 | 9.4 |
| AVX, 4 accumulators | 256-bit | 4 | **13.4** |

The IPC and SIMD gains combine roughly multiplicatively: ~2× from IPC × ~7× from AVX ≈ 13.4×.

---

## SIMD in Python: NumPy as the On-Ramp

You cannot write SIMD instructions directly in Python. But NumPy dispatches its inner loops to compiled SIMD code automatically when:

1. The input is a `numpy.ndarray` with a **fixed dtype** (e.g., `np.float64`, `np.uint32`).
2. The operation is a standard numeric operation (`np.sum`, `np.dot`, arithmetic operators, etc.).
3. The data is **contiguous** in memory (C-order or Fortran-order, not strided or object-dtype).

```python
import numpy as np

# ⚠️ Python list — no SIMD, one element at a time
data = [1, 2, 3, ...]
total = sum(data)

# ✅ NumPy typed array — SIMD loop dispatched automatically
data = np.array([1, 2, 3, ...], dtype=np.uint32)
total = np.sum(data)   # internally: AVX2 or SSE2 reduction loop
```

### What kills NumPy SIMD

| Condition | Effect |
|---|---|
| `dtype=object` (Python objects in array) | No SIMD — type dispatch per element |
| Non-contiguous / strided array (`arr[::2]`) | May disable vectorization |
| Complex branching on each element | Hard to auto-vectorize; use `np.where` for masked ops |
| Pure Python loop over the array | Interpreter overhead dominates — move the loop into NumPy |

---

## Data Shape for Vectorization

Operations that map cleanly to SIMD:
- Bulk reductions: `sum`, `mean`, `max`, `min`
- Element-wise arithmetic: `arr * scale`, `arr + offset`, `arr ** 2`
- Comparisons / masks: `arr > threshold` → boolean mask
- Dot products / matrix multiplications: `np.dot`, `@` operator

Operations that are harder:
- Per-element branching with different computation paths (`if x > 0: do A else: do B`)
  → Use `np.where(arr > 0, result_A, result_B)` where possible
- Variable-length dependencies between elements
- String or categorical operations

---

## SIMD Review Checklist

- [ ] Is the data stored as a typed, homogeneous NumPy array (`dtype=np.float64`, `np.uint32`, etc.)? → If not, convert at creation time.
- [ ] Are bulk numeric operations using NumPy functions rather than Python loops? → Replace loops with NumPy equivalents.
- [ ] Is the array contiguous in memory? → Avoid heavy striding in the hot path; use `np.ascontiguousarray` if needed.
- [ ] Does the loop have complex branching per element? → Try `np.where` or masked indexing; document if SIMD is not achievable.
- [ ] Are SIMD accumulators independent? → Use multiple NumPy operations that don't depend on each other's output where possible.

---

## Key Takeaway

SIMD delivers up to 7–16× on top of clean scalar code. In Python, NumPy is the standard on-ramp — but it only activates when the data is typed and the operation is a standard bulk numeric one. Pure Python loops over numbers, or object-dtype arrays, completely forfeit the SIMD multiplier.
