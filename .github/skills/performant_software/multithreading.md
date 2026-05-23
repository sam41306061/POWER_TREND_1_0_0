---
name: multithreading
description: |
  Multiplier 5 — separability, super-linear cache effect, GIL and ProcessPoolExecutor.
  Trigger phrases: "multithreading", "ProcessPoolExecutor", "GIL", "Multiplier 5",
  "parallel execution", "spread across cores"
argument-hint: "Describe the associative operation or embarrassingly parallel workload to parallelize"
---

# Multithreading — Multiplier 5: Spreading Work Across Cores

**Source:** Computer Enhance Course — Prologue  
**See also:** [five_multipliers.md](five_multipliers.md), [memory_hierarchy_and_caching.md](memory_hierarchy_and_caching.md)

---

## Core Principle

The previous four multipliers all extract more performance from a **single core**. Multithreading is the only multiplier that uses additional cores. Every unused core is a free multiplier left on the table — and that multiplier grows with every CPU generation.

| Hardware | Single-thread penalty |
|---|---|
| 4-core desktop | ~4× |
| 16-core desktop | ~16× |
| 96-core server | ~96× |

On a 96-core server, refusing to use the other cores is roughly the same performance cost as writing the entire program in Python instead of C.

---

## Cores vs. Threads

| Concept | What it is |
|---|---|
| **Core** | A physical execution unit on the CPU die — its own register file, front end, L1, L2 |
| **Thread** | An OS abstraction — a request for an independent instruction stream, scheduled onto a core |

You don't address cores directly. You spawn threads; the OS assigns them to cores.

---

## How Multithreading Differs from IPC and SIMD

| Multiplier | Where parallelism lives | Who creates it |
|---|---|---|
| **IPC** | Independent instructions within one stream | CPU, automatically |
| **SIMD** | Independent data within one instruction | Programmer (packed ops) |
| **Multithreading** | Independent instruction streams | Programmer (explicit partitioning) |

IPC and SIMD extract parallelism from a serially written program. Multithreading requires the programmer to **divide the work** into independent streams explicitly.

---

## The Separability Requirement

Work can be multithreaded when it can be split into independent slices and combined at the end.

**Trivially separable (associative operations):** sum, count, max, min, independent transforms — give each thread a slice; combine partials at the end.

**Not trivially separable:** operations where each step depends on the previous (e.g., a stateful parser, a running total where order is contractually required).

> **Test:** *If I give the first half of the data to Thread A and the second half to Thread B, can I combine their results to get the same answer?*  
> If yes → separable. If no → requires synchronization or redesign.

---

## The Super-Linear Cache Effect

This is the most important non-obvious result in multithreading:

When a dataset is **too large for one core's L1/L2 but small enough that N cores' L1/L2 caches can hold it in aggregate**, splitting across N threads delivers more than N× speedup — because each thread's slice now lives in a fast private cache instead of the shared, slower L3.

**Example:**

| Config | Working set per core | Cache tier hit | Adds / cycle |
|---|---|---|---|
| 1 thread, 64 KB dataset | 64 KB (spills 32 KB L1) | L2 | ~7 |
| 4 threads, 64 KB dataset | 16 KB each (fits in L1) | L1 | **~50+** |

**~7× speedup from 4 cores** — more than 4× — because splitting the work also split the working set across four private L1 caches.

> **General principle:** when the single-threaded bottleneck is the cache hierarchy (not arithmetic), multithreading delivers a computation multiplier *and* a caching multiplier simultaneously.

---

## The Memory Bandwidth Ceiling

When the dataset is much larger than L3 (DRAM-bound), adding threads helps very little:

| Config | Adds / cycle | Speedup |
|---|---|---|
| 1 thread, 128 MB dataset | ~1.4 | 1.0× |
| 4 threads, 128 MB dataset | <3 | <2× |

DRAM bandwidth is a shared resource. On many chips, a single core can already saturate most of the available memory bandwidth. Adding cores buys some additional bandwidth, but nowhere near linearly.

**Rule:** if the working set is in DRAM, fix the cache problem first (see [memory_hierarchy_and_caching.md](memory_hierarchy_and_caching.md)). Then revisit threading.

---

## Python Threading Caveat: the GIL

Python's **Global Interpreter Lock (GIL)** prevents multiple threads from executing Python bytecode simultaneously. For CPU-bound Python code, `threading.Thread` provides no speedup.

| Use case | Correct tool |
|---|---|
| CPU-bound Python code | `concurrent.futures.ProcessPoolExecutor` (separate processes, no GIL) |
| I/O-bound work (network, disk) | `concurrent.futures.ThreadPoolExecutor` (GIL releases during I/O) |
| NumPy operations | NumPy releases the GIL internally — threads work for pure NumPy |

```python
from concurrent.futures import ProcessPoolExecutor
import numpy as np

def process_chunk(chunk):
    return np.sum(chunk)

data = np.arange(1_000_000, dtype=np.uint32)
chunks = np.array_split(data, 4)

with ProcessPoolExecutor(max_workers=4) as pool:
    partials = list(pool.map(process_chunk, chunks))

total = sum(partials)
```

**Process overhead is significant** — only worth it when each chunk is large enough to amortize process-spawn cost (~tens of thousands of elements minimum; benchmark both ways).

---

## Multithreading Review Checklist

- [ ] Can the work be split into independent slices? → Verify associativity; identify partial-result combination.
- [ ] Is the bottleneck compute or memory? → If DRAM-bound, fix cache first.
- [ ] Is the dataset large enough to justify thread/process overhead? → < ~10,000 elements: benchmark before committing.
- [ ] Could multithreading provide a super-linear cache benefit? → Check if N slices each fit in a core's private L1/L2.
- [ ] Is this Python CPU-bound? → Use `ProcessPoolExecutor`, not `ThreadPoolExecutor`.

---

## Key Takeaway

Multithreading is the only multiplier that requires **whole-program partitioning** by the programmer. Its potential magnitude is unique: on modern servers it is the same order as eliminating all interpreter waste. But it is also the multiplier most easily blocked by the wrong data access pattern — a DRAM bottleneck kills scaling regardless of core count.

---

## Handoff Menu

| Next Step | Trigger | Skill |
|---|---|---|
| Check cache behavior first (Multiplier 4) | "cache miss", "memory hierarchy" | [memory_hierarchy_and_caching.md](memory_hierarchy_and_caching.md) |
| Measure scaling efficiency | "benchmark", "bandwidth ceiling" | [measuring_performance.md](measuring_performance.md) |
| Apply the fix to a handler | "implement handler" | `lifecycle-workflows/implement-handler` |
