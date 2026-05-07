# Measuring Performance: Throughput, Latency, and Repetition Testing

**Source:** Computer Enhance Course — Parts 2 & 3  
**See also:** [five_multipliers.md](five_multipliers.md)

---

## Before You Optimize: Know Your Ceiling

The multipliers tell you *how* to go faster. Before applying any of them, answer a more fundamental question:

> **How fast *should* this code be running?**

Without a ceiling, an optimization has no reference point. You don't know if you are at 10% of peak or 95%.

---

## Latency vs. Throughput

These two metrics describe performance from opposite angles.

| Term | Definition | Units | Better = |
|---|---|---|---|
| **Latency** | Time to complete one operation end-to-end | time / operation | lower |
| **Throughput** | Rate at which completed operations emerge when the pipeline is full | operations / time | higher |
| **Reciprocal Throughput** | `1 / throughput` — converts to same units as latency | time / operation | lower |

### The laundry analogy

Two machines that each take 1 hour — one combo washer-dryer vs. a separate washer + dryer:

| Config | Latency (per load) | Throughput | Reciprocal Throughput |
|---|---|---|---|
| Combo | 2 hr | 0.5 loads/hr | 2 hr/load |
| Split | 2 hr | 1.0 load/hr | **1 hr/load** |

The split machines deliver the same latency per load but **twice the throughput** — because two stages run simultaneously. Latency measures the experience of one item; throughput measures the rate of the system.

### Why they differ

- **Latency** is determined by the **dependency chain** within one operation — each step must complete before the next begins.
- **Throughput** is determined by how many operations can be **in-flight simultaneously** — independent operations can overlap.

> **Watch out:** reference tables often say "throughput" when they mean *reciprocal* throughput. If the number is in time-per-operation rather than operations-per-time, it is reciprocal throughput. Always check units.

---

## Bandwidth (Data Throughput)

For data-movement–bound code, the relevant ceiling is **memory bandwidth**:

$$\text{Bandwidth} = \frac{\text{bytes processed}}{\text{time elapsed}}$$

Typical modern consumer CPU: ~35–50 GB/s DRAM bandwidth.

**How to estimate the floor:** identify the minimum data the program *must* read regardless of how the processing is optimized. That read rate sets an absolute ceiling — processing cannot be faster than the time required to load the data.

- If your loop touches `N` elements of `B` bytes each per second, it needs `N × B` bytes/second from memory.
- Compare against the hardware spec. If you are near it, memory is the bottleneck and algorithmic optimization won't help much.

---

## Repetition Testing: Finding the Best-Case Rate

A single run of a program reflects the hidden state of the machine at that moment:
- What is cached at each cache level?
- What has the OS cached?
- Where is the branch predictor pointed?
- Is the CPU thermally throttled?

All of this variability produces noise. **Repetition testing** cuts through it by running the same snippet in a tight loop and taking the **minimum** elapsed time across all repetitions:

```
while (still finding new minimums):
    run the code snippet
    record elapsed time
    if elapsed < current_minimum:
        update minimum
        reset the trial clock    ← keep going after every new record
```

By repeating, the cache, branch predictor, and OS page cache all "train up" on this exact code. Once trained, variability collapses and measurements stabilize near the true best-case rate.

### Min / Avg / Max and when to use each

| Statistic | What it represents | Use for |
|---|---|---|
| **Min** | All components aligned in your favor | Comparing against the hardware ceiling |
| **Avg** | Typical user-visible performance | Estimating real-world throughput |
| **Max** | Maximum interference / worst case | Latency-sensitive or real-time applications |

Repetition testing targets the **minimum** — to understand how close to the hardware ceiling you are.

> **Important caveat:** the minimum is the *probable* best case, not a guaranteed one. Code paths involving heavyweight OS operations (page faults, disk I/O) will have more residual variability than pure in-process computation.

---

## Practical Profiling Workflow

### Step 1: Find the hot path

Before measuring anything, identify the code that runs most often or processes the most data. Optimizing 1% of execution time cannot exceed 1.01× overall speedup regardless of what you do.

Tools:
- Python: `cProfile`, `py-spy`, `line_profiler`
- General: wall-clock timing with `time.perf_counter()` around specific blocks

### Step 2: Estimate the working set tier

```python
working_set_bytes = num_elements * bytes_per_element
```

| Result | Tier | Throughput ceiling |
|---|---|---|
| < 32 KB | L1 | Highest |
| < 256 KB | L2 | High |
| < 8 MB | L3 | Medium |
| Larger | DRAM | Low — bandwidth-bound |

### Step 3: Measure throughput, compare to ceiling

```python
import time
import numpy as np

data = np.random.randint(0, 100, size=1_000_000, dtype=np.uint32)
bytes_processed = data.nbytes

# Repetition test: take the minimum over many runs
min_time = float('inf')
for _ in range(100):
    start = time.perf_counter()
    result = np.sum(data)
    elapsed = time.perf_counter() - start
    min_time = min(min_time, elapsed)

gb_per_sec = (bytes_processed / min_time) / 1e9
print(f"Best-case throughput: {gb_per_sec:.2f} GB/s")
```

Compare against:
- L1 bandwidth (~300+ GB/s typical)
- DRAM bandwidth (~35–50 GB/s typical)
- Hardware spec for your exact chip

### Step 4: Apply multipliers in order

1. If throughput is << DRAM bandwidth → the bottleneck is compute or access pattern, not memory. Apply Waste → IPC → SIMD.
2. If throughput is ~= DRAM bandwidth → memory-bound. Fix the access pattern or working set size first. See [memory_hierarchy_and_caching.md](memory_hierarchy_and_caching.md).

---

## Measurement Review Checklist

- [ ] Have you identified the hot path before optimizing anything?
- [ ] Have you estimated the working set size and assigned it to a cache tier?
- [ ] Are you measuring **minimum** elapsed time (not first-run or average) when benchmarking?
- [ ] Have you computed GB/s and compared it against the hardware ceiling for your tier?
- [ ] Are you timing only the code under test — not setup, teardown, or allocation?

---

## Key Takeaway

Measurement comes before optimization. The minimum of many repetitions is the number to trust — it reflects the system's peak capability without cold-start noise. Comparing that number against the hardware bandwidth ceiling tells you exactly how much room for improvement remains and which multiplier to apply next.
