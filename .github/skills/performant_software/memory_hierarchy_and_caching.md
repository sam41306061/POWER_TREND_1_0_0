# Memory Hierarchy and Caching — Multiplier 4

**Source:** Computer Enhance Course — Prologue  
**See also:** [five_multipliers.md](five_multipliers.md)

---

## Core Principle

All previous multipliers (waste, IPC, SIMD) assume the data the CPU needs is already *inside* the CPU when an instruction asks for it. When the **cache hierarchy** fails to deliver data in time, every other multiplier collapses behind the wait.

Caching does not change which arithmetic gets executed; it changes how fast that arithmetic's **operands arrive**. A ~9× swing in throughput from changing only the buffer size — with zero code changes — is real and common.

---

## Loads and Stores

Every arithmetic instruction that reads memory is actually two operations:

| Operation | What it does |
|---|---|
| **load** | Read a value from memory into the CPU |
| **arithmetic** | Compute the result once the value has arrived |

The arithmetic cannot execute until the load completes. If loads are slow, all other work lines up behind them — regardless of how many execution units the CPU has.

**Accumulators** (like a running sum) live in the CPU's **register file** — on-die, effectively zero-latency. The data being read each iteration does not.

---

## The Memory Hierarchy

A modern CPU has a stack of increasingly large, increasingly slow storage tiers. The CPU walks from the closest tier outward until it finds the data.

| Tier | Typical latency | Typical size | Scope |
|---|---|---|---|
| **Register file** | 0 cycles (bypass) | ~hundreds of values | Per core |
| **L1 cache** | ~3–4 cycles | ~32 KB | Per core |
| **L2 cache** | ~14 cycles | ~256 KB | Per core |
| **L3 cache** | ~80 cycles | ~8 MB | Shared across cores |
| **DRAM** | ~hundreds of cycles | ~16 GB+ | Off-die |

Key properties:
- Each tier is **faster but smaller** than the next. Physical distance from the execution unit becomes latency.
- Caches are transistors **on the CPU die**. DRAM is physically separate.
- Bandwidth shrinks down the hierarchy roughly in lockstep with latency growth. A cache miss costs on both axes simultaneously.
- The **per-core / shared split** is typically between L2 and L3. Each core has its own L1 + L2; all cores share one L3.

> **Practical rule of thumb:**  
> Estimate working set size = `num_elements × bytes_per_element`.  
> Assign it to a tier. That tier is your **performance ceiling** for that loop.

---

## The Cache Effect in Numbers

Same loop, same code, four different buffer sizes (only the buffer size changes):

| Buffer size | Where it lives | Adds / cycle | Slowdown vs. L1 |
|---|---|---|---|
| 16 KB | L1 | **13.2** | 1.0× |
| 128 KB | L2 | 7.7 | ~1.7× |
| 1 MB | L3 | 4.4 | ~3.0× |
| 128 MB | DRAM | 1.4 | **~9.4×** |

The DRAM-bound case barely beats the **naive scalar loop** — all the SIMD and IPC gains are wiped out by memory latency.

**Cache behavior is a multiplier comparable in size to IPC and SIMD combined.**

---

## Access Pattern: Sequential vs. Random

Hardware **prefetchers** detect sequential memory access patterns and load the next cache line before it is needed — but only for sequential access.

| Pattern | Prefetcher friendly? | Effect |
|---|---|---|
| Walk array index 0 → N | ✅ Yes | Loads arrive before the instruction needs them |
| Random index access | ❌ No | Every load is a cache miss with full latency penalty |
| Linked-list traversal | ❌ No | Pointer chasing — each load reveals the next address |
| Dict lookup in hot path | ❌ No | Hash + pointer chain = random access |

**Rule:** hot loops must access memory in a straight line (or close to it).

---

## Data Layout: Struct of Arrays vs. Array of Structs

A common cause of poor cache utilization is iterating a field from a struct when each struct also contains many other fields.

```python
# ⚠️ Array of Structs — iterating only 'price' reads the whole struct into cache
class Bar:
    open: float
    high: float
    low: float
    close: float   # we only need this
    volume: int

bars: list[Bar]  # accessing bar.close strides through unneeded fields

# ✅ Struct of Arrays — iterating 'close' accesses a dense packed array
closes: np.ndarray   # all close prices, contiguous in memory
```

When only one field is needed in the hot loop, **struct of arrays** keeps the cache line full of useful data.

---

## Chunking for Cache Efficiency

If the full dataset is larger than the cache, process it in **cache-sized chunks**:

```python
CHUNK = 8_000   # tune so chunk fits in L1/L2

for start in range(0, len(data), CHUNK):
    chunk = data[start : start + CHUNK]
    process(chunk)   # all accesses to chunk stay in cache
```

This is also the mechanism behind multithreading's **super-linear** speedup: splitting work across N cores gives each core a smaller slice, which may fit in that core's private L1/L2 even when the full dataset does not.

---

## Cache Review Checklist

- [ ] What tier does the working set live in? (< 32 KB → L1, < 256 KB → L2, < 8 MB → L3, else DRAM)
- [ ] Is the hot loop accessing memory sequentially? → If not, restructure.
- [ ] Is the hot loop reading one field of a wide struct? → Consider struct-of-arrays layout.
- [ ] Could the problem be split into cache-sized chunks? → Do so before adding threads.
- [ ] If the working set is in DRAM: the bottleneck is the memory bus, not the CPU. Restructure data access first; then consider multithreading.

---

## Key Takeaway

Cache behavior can wipe out a 10× SIMD win with no code change — just a larger input. Always estimate the working set tier **before** spending time on IPC or SIMD optimizations. If the data doesn't fit in L1/L2, fix that first.
