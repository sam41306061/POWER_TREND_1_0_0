# Waste — Multiplier 1: Eliminating Unnecessary Instructions

**Source:** Computer Enhance Course — Prologue  
**See also:** [five_multipliers.md](five_multipliers.md)

---

## Core Principle

**Waste** = CPU instructions that execute but contribute *nothing* to the computation you actually requested.

The first and largest lever in performance is simply **reducing the total number of instructions**. Every optimization in this category produces zero algorithmic change — the result is identical; only the instruction count differs.

> "We don't need optimization. All we need is to come back to our senses and not write programs that are doing 181 instructions instead of one."

---

## The A+B Benchmark

The canonical illustration: how many CPU instructions does it take to add two integers?

| Language | Instructions to execute `A + B` |
|---|---|
| C (optimized) | **1** — `lea eax, [rcx+rdx]` |
| Python 3.11 | **~181** |

Python's 181 instructions come from: bytecode decoding and dispatch, type-checking and method resolution, heap allocation of the result integer, and reference count updates on the operands. Only **one** of those 181 instructions is the actual addition.

### Real-world impact (4,096-element integer sum)

| | Python | C (unoptimized) |
|---|---|---|
| Adds per clock cycle | 0.006 | 0.85 |
| Relative speed | 1× | **~130×** |

The C program is ~130× faster with **no algorithmic change** — it simply eliminates the interpreter overhead.

---

## Why Interpreted Languages Are Slow

Interpreted languages maintain a second instruction stream (bytecode) the CPU doesn't natively understand. At runtime the interpreter must decode and manage that stream on every operation, multiplying instruction count by the overhead of: type dispatch, object allocation, reference counting, and interpreter-loop bookkeeping.

**Language choice is a performance decision.** Budget for the interpreter multiplier or route around it.

---

## Strategies to Reduce Waste

### 1. Move work out of loops

Any computation that produces the same result on every iteration should be computed once before the loop:

```python
# ⚠️ Recomputes len(arr) every iteration
for i in range(len(arr)):
    ...

# ✅ Compute once
n = len(arr)
for i in range(n):
    ...
```

### 2. Replace manual loops with builtins

Python builtins (`sum`, `max`, `min`, `any`, `all`) run compiled C code — ~10× faster than a manual Python loop:

```python
# ⚠️ Manual accumulation in Python
total = 0
for v in arr:
    total += v

# ✅ Builtin runs in C
total = sum(arr)
```

### 3. Call into compiled libraries for bulk work

NumPy, Pandas, and similar libraries execute their inner loops in compiled code. Python only pays interpreter overhead at the call boundary, not per element:

```python
# ⚠️ Element-by-element in Python interpreter
result = [x * 2 for x in arr]

# ✅ Entire operation dispatched to C/SIMD loop
result = np.array(arr) * 2
```

### 4. Use typed arrays, not Python lists

A `list` stores Python objects (each with type tag + reference count). An `array.array` or `numpy.ndarray` with a dtype stores raw C values — no per-element type dispatch:

```python
import array
typed = array.array('I', data)   # 'I' = unsigned 32-bit int — raw C buffer
```

### 5. JIT or native extensions for irreducible hot paths

| Escalation | Mechanism |
|---|---|
| `numba.jit` | JIT-compiles Python functions to native code at first call |
| Cython | Translates annotated Python to C; compile once |
| C/Rust extension | Write the hot path natively; call from Python |

---

## Waste Review Checklist

- [ ] Is the hot loop written in pure Python with no compiled code inside it? → This is the highest-priority fix.
- [ ] Are there operations inside the loop that don't depend on loop state? → Move them outside.
- [ ] Is a builtin available to replace the loop? → Use it.
- [ ] Is the data a plain Python `list` of numbers? → Convert to `array.array` or `numpy.ndarray`.
- [ ] Are bulk numeric operations using NumPy or a vectorized library? → They should be.

---

## Key Takeaway

Eliminating waste requires **no algorithmic cleverness**. The 130× speedup above came from zero algorithmic change — only from removing interpreter overhead. This is also why language choice matters more for performance-critical code than almost any micro-optimization within the language.
