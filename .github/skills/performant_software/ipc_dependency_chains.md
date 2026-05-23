---
name: ipc-dependency-chains
description: |
  Multiplier 2 — serial dependency chains, multiple-accumulator fix, loop overhead.
  Trigger phrases: "IPC", "dependency chains", "instruction-level parallelism", "Multiplier 2",
  "accumulator pattern", "serial dependency"
argument-hint: "Paste the loop or accumulator code you want to parallelize"
---

# IPC — Multiplier 2: Instructions Per Clock and Dependency Chains

**Source:** Computer Enhance Course — Prologue  
**See also:** [five_multipliers.md](five_multipliers.md), [waste_and_instructions.md](waste_and_instructions.md)

---

## Core Principle

Even a program with zero wasted instructions can run far below hardware potential. A modern CPU can execute **more than one instruction per clock cycle** — but only when those instructions do not depend on each other's outputs.

**IPC (Instructions Per Clock)** measures how many instructions the CPU retires per cycle.  
**ILP (Instruction-Level Parallelism)** is the CPU capability that makes IPC > 1 possible.

When instructions form a **serial dependency chain**, no amount of ILP helps — the CPU is forced to execute each one in order, waiting for the previous result.

---

## Latency vs. Throughput (Conceptual Foundation)

| Term | Definition | Units | Better = |
|---|---|---|---|
| **Latency** | Time to complete one operation end-to-end | time / operation | lower |
| **Throughput** | Rate at which completed operations emerge | operations / time | higher |
| **Reciprocal Throughput** | `1 / Throughput` — aligns units with latency | time / operation | lower |

These two metrics diverge whenever operations can be **overlapped**. A pipeline of independent operations has the same per-operation latency, but a much better reciprocal throughput because multiple operations are in-flight simultaneously.

> Many reference tables say "throughput" when they mean *reciprocal throughput*. Always check the units.

---

## Serial Dependency Chains — The IPC Killer

A **dependency chain** is a sequence of operations where each step can only begin after the previous step produces its result.

### Classic example: single-accumulator summation

```python
total = 0
for v in arr:
    total += v   # each add reads the OUTPUT of the previous add
```

The dependency graph:

```
add₀ → add₁ → add₂ → add₃ → … → addₙ
```

Every add must wait for the previous one to complete. The CPU cannot issue two of them simultaneously, no matter how many execution units it has. The ceiling is **~1 add per cycle**, regardless of the hardware's theoretical IPC.

### Why the CPU can't fix this itself

The CPU can only inspect the **operands** of each instruction to detect independence. It cannot reason about mathematical properties of the computation. It sees that `total` is both a source and destination of every add — so it must serialize them. The programmer must break the chain explicitly.

---

## Breaking the Chain: Multiple Accumulators

Integer addition is **associative and commutative** — reordering or regrouping additions does not change the result. This lets us create independent sub-chains:

```python
# ⚠️ Single accumulator — serial chain, ~1 add/cycle
total = 0
for i in range(0, len(arr), 2):
    total += arr[i]
    total += arr[i + 1]

# ✅ Two independent accumulators — parallel chains, ~2 adds/cycle
a, b = 0, 0
for i in range(0, len(arr), 2):
    a += arr[i]
    b += arr[i + 1]
total = a + b
```

With two accumulators, `a` and `b` share no operands. The CPU can issue one add from each chain simultaneously. Four accumulators roughly double throughput again.

### Measured results (C scalar summation loop)

| Strategy | Accumulators | Adds / cycle |
|---|---|---|
| Single accumulator | 1 | 0.99 |
| Dual accumulators | 2 | 1.27 |
| Quad accumulators | 4 | 1.95 |

Two accumulators immediately break through the 1 add/cycle ceiling. The ceiling rises linearly with the number of independent chains — up to the CPU's execution unit limit.

---

## Loop Overhead Waste

A secondary IPC issue: every iteration of a loop also executes counter-increment and compare instructions that are not part of the useful work.

```python
# ⚠️ Builds a range object, does index computation every iteration
for i in range(len(arr)):
    process(arr[i])

# ✅ Iterates directly — no index, no range object
for value in arr:
    process(value)
```

**Loop unrolling** (doing N iterations' worth of work per loop body) reduces the ratio of loop-maintenance instructions to useful instructions — but cannot break a serial dependency chain. Unrolling alone is insufficient when the bottleneck is the chain itself.

---

## IPC Review Checklist

- [ ] Does the hot loop use a single accumulator that is read and written every iteration? → Split into 2–4 independent accumulators.
- [ ] Is there avoidable loop-counter overhead (`range(len(arr))` when index isn't needed)? → Use `for value in arr`.
- [ ] Have you confused loop unrolling with dependency-chain breaking? → Unrolling only helps if loop overhead is the bottleneck; it does nothing for serial dependency chains.
- [ ] Are there other reads in the loop that feed back into themselves? → Identify all induction variables and check each one for serial dependence.

---

## Key Takeaway

The IPC multiplier is modest (~2–4×) because modern CPUs are already fairly aggressive at exploiting the ILP they can find. But serial dependency chains are invisible to tools that only measure time — the code *looks* correct and runs at "1 add per cycle," which sounds fast until you realize the hardware ceiling is 4+. The fix is a one-line restructure of the accumulator pattern.

---

## Handoff Menu

| Next Step | Trigger | Skill |
|---|---|---|
| Check if SIMD gives more gain (Multiplier 3) | "SIMD", "vectorize" | [simd_vectorization.md](simd_vectorization.md) |
| Check if cache is the real bottleneck (Multiplier 4) | "cache miss", "memory hierarchy" | [memory_hierarchy_and_caching.md](memory_hierarchy_and_caching.md) |
| Measure before and after | "benchmark" | [measuring_performance.md](measuring_performance.md) |
| Apply the fix to a handler | "implement handler" | `lifecycle-workflows/implement-handler` |
