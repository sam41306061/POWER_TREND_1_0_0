# The Five Multipliers of Performance

**Source:** Computer Enhance Course (Performance-Aware Programming)  
**Category:** performant_software  
**Status:** ✅ Populated — derived from core course material

---

## The Framework

There are only **two levers** that improve program performance:

1. **Reduce the total number of instructions** fed into the CPU.
2. **Increase the efficiency** of those instructions as they move through the CPU.

Every practical optimization technique maps to one of these two levers. The five multipliers below are the primary ways to pull them.

---

## The Five Multipliers

| # | Multiplier | Typical gain | Lever |
|---|---|---|---|
| 1 | **Waste** | 10–1,000× | Fewer instructions per unit of work |
| 2 | **IPC** | ~2–4× | Independent dependency chains let the CPU do more per clock |
| 3 | **SIMD** | ~4–16× | One instruction processes many values at once |
| 4 | **Caching** | ~2–10× | Keep data close to the CPU so loads don't stall the loop |
| 5 | **Multithreading** | ~N cores (sometimes more) | Spread independent work across multiple cores |

> Multipliers **compound**: Waste × IPC × SIMD × Caching × Multithreading. On a modern multi-core machine, the gap between naive code and hardware-aware code is easily four to five orders of magnitude.

---

## Correct Order of Attack

Work through the multipliers in order. Each one assumes the previous has been addressed:

1. **Waste first** — if the code is doing 181 instructions where 1 would do, IPC gains on those 181 are irrelevant.
2. **IPC** — once instruction count is sane, restructure for parallel execution units.
3. **SIMD** — once dependency chains are broken, widen the arithmetic per instruction.
4. **Caching** — even perfect arithmetic collapses if data doesn't arrive in time.
5. **Multithreading** — finally, spread the optimized work across all available cores.

---

## Cumulative Example (integer summation loop)

| Stage | Adds / cycle | Speedup vs. Python |
|---|---|---|
| Python loop | 0.004 | 1× |
| C scalar (waste eliminated) | 0.85 | ~194× |
| C scalar + 4 accumulators (IPC) | 1.95 | ~446× |
| C AVX + 4 accumulators (SIMD) | 13.4 | ~3,000× |
| C AVX + 4 accumulators, 4 threads on 64 KB (MT + cache) | ~50+ | **super-linear** |

---

## Key Mental Models

- **Measure before optimizing.** You can't improve what you don't understand. Find the hot path first.
- **The hot path is what matters.** A 10× speedup on 1% of the code = 1.1× overall. Optimize the loop that runs most.
- **Estimate data size first.** This tells you which cache tier the working set lives in, which determines the ceiling for all other multipliers.
  - < 32 KB → **L1** (fastest)
  - < 256 KB → **L2**
  - < 8 MB → **L3**
  - Larger → **DRAM** (~9× slower than L1)

---

## Skill Files in This Directory

| File | Multiplier |
|---|---|
| [waste_and_instructions.md](waste_and_instructions.md) | 1 — Waste |
| [ipc_dependency_chains.md](ipc_dependency_chains.md) | 2 — IPC |
| [simd_vectorization.md](simd_vectorization.md) | 3 — SIMD |
| [memory_hierarchy_and_caching.md](memory_hierarchy_and_caching.md) | 4 — Caching |
| [multithreading.md](multithreading.md) | 5 — Multithreading |
| [measuring_performance.md](measuring_performance.md) | Cross-cutting — Measurement |
