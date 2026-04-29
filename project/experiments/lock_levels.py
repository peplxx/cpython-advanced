"""lock_levels: threading.Lock vs asyncio.Lock vs multiprocessing.Lock.

threading.Lock:        futex CAS in userspace when uncontended — ~50-100 ns.
asyncio.Lock:          pure Python (collections.deque + Future) — zero syscalls.
multiprocessing.Lock:  semaphore-backed — kernel involved even uncontended.

asyncio.Lock cannot be meaningfully compared at the OS level
"""

import asyncio
import multiprocessing
import sys
import threading
import time

import pandas as pd

ITERATIONS = 500_000


def _row(lock_type: str, elapsed: float, iterations: int) -> dict:
    return {
        "lock":           lock_type,
        "iterations":     iterations,
        "time_s":         round(elapsed, 4),
        "ns_per_acquire": round(elapsed / iterations * 1e9, 1),
    }


def bench_threading_lock(iterations: int = ITERATIONS) -> pd.DataFrame:
    lock = threading.Lock()
    t0 = time.perf_counter()
    for _ in range(iterations):
        with lock:
            pass
    return pd.DataFrame([_row("threading.Lock", time.perf_counter() - t0, iterations)])


async def _bench_asyncio(iterations: int) -> float:
    lock = asyncio.Lock()
    t0 = time.perf_counter()
    for _ in range(iterations):
        async with lock:
            pass
    return time.perf_counter() - t0


def bench_asyncio_lock(iterations: int = ITERATIONS) -> pd.DataFrame:
    elapsed = asyncio.run(_bench_asyncio(iterations))
    return pd.DataFrame([_row("asyncio.Lock", elapsed, iterations)])


def bench_multiprocessing_lock(iterations: int = ITERATIONS) -> pd.DataFrame:
    lock = multiprocessing.Lock()
    t0 = time.perf_counter()
    for _ in range(iterations):
        with lock:
            pass
    return pd.DataFrame([_row("multiprocessing.Lock", time.perf_counter() - t0, iterations)])


if __name__ == "__main__":
    from pathlib import Path

    df = pd.concat([
        bench_threading_lock(),
        bench_asyncio_lock(),
        bench_multiprocessing_lock(),
    ], ignore_index=True)

    if "--output" in sys.argv:
        output = Path(sys.argv[sys.argv.index("--output") + 1])
        df.to_json(output)
    else:
        print(df.to_string(index=False))
