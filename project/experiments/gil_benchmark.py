"""GIL benchmark: CPU-bound task — 1 thread vs N threads."""

import sys
import threading
import time

import pandas as pd

WORKLOAD = 10_000_000


def _cpu_task(n: int) -> int:
    total = 0
    for i in range(n):
        total += i * i
    return total


def _bench(threads: int, total_workload: int = WORKLOAD) -> dict:
    chunk = total_workload // threads
    workers = [threading.Thread(target=_cpu_task, args=(chunk,)) for _ in range(threads)]
    t0 = time.perf_counter()
    for w in workers: w.start()
    for w in workers: w.join()
    return {
        "threads":        threads,
        "time_s":         round(time.perf_counter() - t0, 3),
    }


def run_single(total_workload: int = WORKLOAD) -> pd.DataFrame:
    return pd.DataFrame([_bench(1, total_workload)])


def run_threaded(total_workload: int = WORKLOAD, thread_counts: tuple = (2, 3, 4, 5, 6, 7, 8)) -> pd.DataFrame:
    return pd.DataFrame([_bench(t, total_workload) for t in thread_counts])


if __name__ == "__main__":
    from pathlib import Path

    df = pd.concat([run_single(), run_threaded()], ignore_index=True)

    if "--output" in sys.argv:
        output = Path(sys.argv[sys.argv.index("--output") + 1])
        df.to_json(output)
    else:
        print(df.to_string(index=False))
