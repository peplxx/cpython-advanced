"""Bounded buffer throughput sweep.

Methodology (per proposal.md):
- fixed total items (default 1_000_000)
- sweep: producers x consumers x capacity
- N runs per scenario, report median wall-clock time
- throughput = items / wall_clock_time
"""

import argparse
import statistics
import sys
import threading
import time
from pathlib import Path

import pandas as pd

from lab.bounded_buffer import IMPLS

POISON = None

DEFAULT_TOTAL    = 1_000_000
DEFAULT_RUNS     = 5
DEFAULT_PRODS    = (1, 2, 4)
DEFAULT_CONS     = (1, 2, 4)
DEFAULT_CAPS     = (1, 10, 100)


def _run_once(impl_cls, n_producers: int, n_consumers: int, capacity: int, total: int) -> float:
    buf = impl_cls(capacity)
    items_per_prod = total // n_producers
    real_total = items_per_prod * n_producers

    def producer():
        for i in range(items_per_prod):
            buf.put(i)

    def consumer():
        while True:
            item = buf.get()
            if item is POISON:
                return

    producers = [threading.Thread(target=producer) for _ in range(n_producers)]
    consumers = [threading.Thread(target=consumer) for _ in range(n_consumers)]

    t0 = time.perf_counter()
    for c in consumers: c.start()
    for p in producers: p.start()
    for p in producers: p.join()
    for _ in consumers: buf.put(POISON)
    for c in consumers: c.join()
    elapsed = time.perf_counter() - t0

    return elapsed, real_total


def sweep(
    total: int = DEFAULT_TOTAL,
    runs: int = DEFAULT_RUNS,
    producers_values=DEFAULT_PRODS,
    consumers_values=DEFAULT_CONS,
    capacity_values=DEFAULT_CAPS,
) -> pd.DataFrame:
    rows = []
    for impl_name, impl_cls in IMPLS.items():
        for n_prod in producers_values:
            for n_cons in consumers_values:
                for cap in capacity_values:
                    times = []
                    items = 0
                    for _ in range(runs):
                        elapsed, items = _run_once(impl_cls, n_prod, n_cons, cap, total)
                        times.append(elapsed)
                    median = statistics.median(times)
                    rows.append({
                        "impl":            impl_name,
                        "producers":       n_prod,
                        "consumers":       n_cons,
                        "capacity":        cap,
                        "items":           items,
                        "runs":            runs,
                        "median_time_s":   round(median, 4),
                        "min_time_s":      round(min(times), 4),
                        "max_time_s":      round(max(times), 4),
                        "throughput_ips":  round(items / median, 1),
                    })
    return pd.DataFrame(rows)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--total",  type=int, default=DEFAULT_TOTAL, help="total items to push (default 1_000_000)")
    parser.add_argument("--runs",   type=int, default=DEFAULT_RUNS,  help="repetitions per scenario (default 5)")
    parser.add_argument("--output", type=Path,                       help="write JSON instead of printing")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    df = sweep(total=args.total, runs=args.runs)

    py = f"{sys.version_info.major}.{sys.version_info.minor}"
    if sys.flags.gil == 0:
        py += "t"
    df.insert(0, "python", py)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        df.to_json(args.output, orient="records", indent=2)
    else:
        print(df.to_string(index=False))
