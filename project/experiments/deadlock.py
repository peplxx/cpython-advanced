"""Deadlock: classic two-RLock scenario and fix via lock ordering."""

import threading
import time

import pandas as pd

DEADLOCK_TIMEOUT = 1.0
WORK_DELAY = 0.5


def start_and_join(workers: list, timeout: float | None = None) -> list[bool]:
    for w in workers: w.start()
    completed = []
    for w in workers:
        w.join(timeout=timeout)
        completed.append(not w.is_alive())
    return completed


def _run_deadlock(configs: list[tuple], timeout: float) -> pd.DataFrame:
    barrier = threading.Barrier(len(configs))
    events: list[dict] = []
    t0 = time.perf_counter()

    def _thread(name, first, first_name, second, second_name):
        with first:
            events.append({"thread": name, "event": f"acquired {first_name}", "time_s": round(time.perf_counter() - t0, 3)})
            barrier.wait()
            with second:
                events.append({"thread": name, "event": f"acquired {second_name}", "time_s": round(time.perf_counter() - t0, 3)})

    workers = [threading.Thread(target=_thread, args=cfg, daemon=True) for cfg in configs]
    completed = start_and_join(workers, timeout=timeout)

    for (name, *_), done in zip(configs, completed):
        events.append({"thread": name, "event": "completed" if done else "DEADLOCKED", "time_s": round(time.perf_counter() - t0, 3)})

    return pd.DataFrame(events).sort_values("time_s").reset_index(drop=True)


def _run_fixed(configs: list[tuple]) -> pd.DataFrame:
    events: list[dict] = []
    t0 = time.perf_counter()

    def _thread(name, first, first_name, second, second_name):
        with first:
            events.append({"thread": name, "event": f"acquired {first_name}", "time_s": round(time.perf_counter() - t0, 3)})
            time.sleep(WORK_DELAY)
            with second:
                events.append({"thread": name, "event": f"acquired {second_name}", "time_s": round(time.perf_counter() - t0, 3)})
                time.sleep(WORK_DELAY)
        events.append({"thread": name, "event": "completed", "time_s": round(time.perf_counter() - t0, 3)})

    workers = [threading.Thread(target=_thread, args=cfg, daemon=True) for cfg in configs]
    start_and_join(workers, timeout=None)

    return pd.DataFrame(events).sort_values("time_s").reset_index(drop=True)


# --- Case 1 & 2: Two threads --------------------------------------------------

def demo_deadlock(timeout: float = DEADLOCK_TIMEOUT) -> pd.DataFrame:
    la, lb = threading.RLock(), threading.RLock()
    return _run_deadlock([("T1", la, "A", lb, "B"), ("T2", lb, "B", la, "A")], timeout)


def demo_fixed() -> pd.DataFrame:
    # global lock order: A < B
    la, lb = threading.RLock(), threading.RLock()
    return _run_fixed([("T1", la, "A", lb, "B"), ("T2", la, "A", lb, "B")])


# --- Case 3 & 4: Three threads ------------------------------------------------

def demo_deadlock_3(timeout: float = DEADLOCK_TIMEOUT) -> pd.DataFrame:
    la, lb, lc = threading.RLock(), threading.RLock(), threading.RLock()
    return _run_deadlock([("T1", la, "A", lb, "B"), ("T2", lb, "B", lc, "C"), ("T3", lc, "C", la, "A")], timeout)


def demo_fixed_3() -> pd.DataFrame:
    # global lock order: A < B < C
    la, lb, lc = threading.RLock(), threading.RLock(), threading.RLock()
    return _run_fixed([("T1", la, "A", lb, "B"), ("T2", lb, "B", lc, "C"), ("T3", la, "A", lc, "C")])


if __name__ == "__main__":
    for label, fn in [
        ("Deadlock (2 threads)", demo_deadlock),
        ("Fixed   (2 threads)", demo_fixed),
        ("Deadlock (3 threads)", demo_deadlock_3),
        ("Fixed   (3 threads)", demo_fixed_3),
    ]:
        print(f"\n=== {label} ===")
        print(fn().to_string(index=False))
