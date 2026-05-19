"""lock_contention: threading vs asyncio vs multiprocessing Lock under contention.

Sweeps worker count to show how each lock type scales with contention.
"""

import asyncio
import multiprocessing
import sys
import threading
import time

import pandas as pd

ITERATIONS    = 200_000
ITERATIONS_MP = 5_000


def _row(lock_type: str, workers: int, elapsed: float, iterations: int) -> dict:
    return {
        "lock":           lock_type,
        "workers":        workers,
        "time_s":         round(elapsed, 4),
        "ns_per_acquire": round(elapsed / iterations * 1e9, 1),
    }


# --- threading.Lock -----------------------------------------------------------

def bench_threading(iterations: int = ITERATIONS, worker_counts: tuple = (1, 2, 3, 4, 5, 6, 7, 8)) -> pd.DataFrame:
    rows = []
    for n in worker_counts:
        lock = threading.Lock()
        times: list[float] = []

        def worker(lock=lock, times=times):
            t0 = time.perf_counter()
            for _ in range(iterations):
                with lock:
                    pass
            times.append(time.perf_counter() - t0)

        workers = [threading.Thread(target=worker) for _ in range(n)]
        for w in workers: w.start()
        for w in workers: w.join()
        rows.append(_row("threading.Lock", n, max(times), iterations))
    return pd.DataFrame(rows)


# --- asyncio.Lock -------------------------------------------------------------

async def _asyncio_contended(iterations: int, n_tasks: int) -> float:
    lock = asyncio.Lock()

    async def task():
        t0 = time.perf_counter()
        for _ in range(iterations):
            async with lock:
                pass
        return time.perf_counter() - t0

    return max(await asyncio.gather(*[task() for _ in range(n_tasks)]))


def bench_asyncio(iterations: int = ITERATIONS, worker_counts: tuple = (1, 2, 3, 4, 5, 6, 7, 8)) -> pd.DataFrame:
    return pd.DataFrame([
        _row("asyncio.Lock", n, asyncio.run(_asyncio_contended(iterations, n)), iterations)
        for n in worker_counts
    ])


# --- multiprocessing.Lock -----------------------------------------------------

def _mp_worker(lock, iterations: int) -> None:
    for _ in range(iterations):
        with lock:
            pass


def bench_multiprocessing(iterations: int = ITERATIONS_MP, worker_counts: tuple = (1, 2, 3, 4, 5, 6, 7, 8)) -> pd.DataFrame:
    rows = []
    for n in worker_counts:
        lock = multiprocessing.Lock()
        procs = [multiprocessing.Process(target=_mp_worker, args=(lock, iterations)) for _ in range(n)]
        t0 = time.perf_counter()
        for p in procs: p.start()
        for p in procs: p.join()
        rows.append(_row("multiprocessing.Lock", n, time.perf_counter() - t0, iterations))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    from pathlib import Path

    df = pd.concat([bench_threading(), bench_asyncio(), bench_multiprocessing()], ignore_index=True)

    if "--output" in sys.argv:
        output = Path(sys.argv[sys.argv.index("--output") + 1])
        df.to_json(output)
    else:
        print(df.to_string(index=False))
