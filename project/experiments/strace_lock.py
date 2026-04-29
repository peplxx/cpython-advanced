"""strace_lock: uncontended vs contended lock acquisition timing.

On Linux, observe futex syscall differences with:
    strace -c -e trace=futex python experiments/strace_lock.py

Uncontended: CAS in userspace — zero futex calls.
Contended:   blocked threads call futex(FUTEX_WAIT); waking thread calls FUTEX_WAKE.
CPython 3.12:  futex(FUTEX_WAIT_BITSET) via sem_timedwait()
CPython 3.13t: futex(FUTEX_WAIT)        via _PyParkingLot
"""

import sys
import threading
import time

import pandas as pd

ITERATIONS = 500_000


def _bench(iterations: int, threads: int) -> dict:
    lock = threading.Lock()
    times = []

    def worker():
        t0 = time.perf_counter()
        for _ in range(iterations):
            with lock:
                pass
        times.append(time.perf_counter() - t0)

    workers = [threading.Thread(target=worker) for _ in range(threads)]
    for w in workers: w.start()
    for w in workers: w.join()

    wall = max(times)
    return {
        "threads":        threads,
        "iterations":     iterations,
        "time_s":         round(wall, 4),
        "ns_per_acquire": round(wall / iterations * 1e9, 1),
    }


def uncontended(iterations: int = ITERATIONS) -> pd.DataFrame:
    return pd.DataFrame([_bench(iterations, threads=1)])


def contended(iterations: int = ITERATIONS, thread_counts: tuple = (2, 3, 4, 5, 6, 7, 8)) -> pd.DataFrame:
    return pd.DataFrame([_bench(iterations, t) for t in thread_counts])


if __name__ == "__main__":
    from pathlib import Path

    df = pd.concat([uncontended(), contended()], ignore_index=True)

    if "--output" in sys.argv:
        output = Path(sys.argv[sys.argv.index("--output") + 1])
        df.to_json(output)
    else:
        print(df.to_string(index=False))
