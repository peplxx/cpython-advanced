"""Race condition on a shared counter: threads and processes, with lock vs without."""

import multiprocessing
import threading
import time

import pandas as pd

# TODO: подумать на счет таймингов и интерпритации результатов
CONTEXT_SWITCH_DELAY = 0.001


def start_and_join(workers: list) -> None:
    for worker in workers: worker.start()
    for worker in workers: worker.join()


# --- Case 1: Threading, no lock -----------------------------------------------

def threading_unsafe(tasks: int, increments: int) -> int:
    counter = [0]

    def increment():
        for _ in range(increments):
            current = counter[0]
            time.sleep(CONTEXT_SWITCH_DELAY)
            counter[0] = current + 1

    start_and_join([threading.Thread(target=increment) for _ in range(tasks)])
    return counter[0]


# --- Case 2: Threading, with lock ---------------------------------------------

def threading_safe(tasks: int, increments: int) -> int:
    counter = [0]
    lock = threading.Lock()

    def increment():
        for _ in range(increments):
            with lock:
                current = counter[0]
                time.sleep(CONTEXT_SWITCH_DELAY)
                counter[0] = current + 1

    start_and_join([threading.Thread(target=increment) for _ in range(tasks)])
    return counter[0]


# --- Case 3: Multiprocessing, no lock ----------------------------------------

def _increment_shared_counter_unsafe(shared_counter, increments: int) -> None:
    for _ in range(increments):
        current = shared_counter.value
        time.sleep(CONTEXT_SWITCH_DELAY)
        shared_counter.value = current + 1


def multiprocessing_unsafe(tasks: int, increments: int) -> int:
    shared_counter = multiprocessing.Value("i", 0, lock=False)
    start_and_join([
        multiprocessing.Process(target=_increment_shared_counter_unsafe, args=(shared_counter, increments))
        for _ in range(tasks)
    ])
    return shared_counter.value


# --- Case 4: Multiprocessing, with lock --------------------------------------

def _increment_shared_counter_safe(shared_counter, lock, increments: int) -> None:
    for _ in range(increments):
        with lock:
            current = shared_counter.value
            time.sleep(CONTEXT_SWITCH_DELAY)
            shared_counter.value = current + 1


def multiprocessing_safe(tasks: int, increments: int) -> int:
    shared_counter = multiprocessing.Value("i", 0, lock=False)
    lock = multiprocessing.Lock()
    start_and_join([
        multiprocessing.Process(target=_increment_shared_counter_safe, args=(shared_counter, lock, increments))
        for _ in range(tasks)
    ])
    return shared_counter.value


# --- Benchmark ----------------------------------------------------------------

class RaceConditionBenchmark:
    cases = [
        ("threading / unsafe", threading_unsafe),
        ("threading / safe  ", threading_safe),
        ("processes / unsafe", multiprocessing_unsafe),
        ("processes / safe  ", multiprocessing_safe),
    ]

    def __init__(self, tasks_values=None, increments=None):
        self.tasks_values = tasks_values or range(2, 6)
        self.increments = increments or 500

    def run(self) -> pd.DataFrame:
        import sys
        python_version = sys.version.split()[0]

        rows = []
        for tasks in self.tasks_values:
            for case_name, fn in self.cases:
                t0 = time.perf_counter()
                result = fn(tasks, self.increments)
                elapsed = time.perf_counter() - t0
                rows.append({
                    "python_version": python_version,
                    "case":           case_name,
                    "tasks":          tasks,
                    "result":         result,
                    "expected":       tasks * self.increments,
                    "time_s":         round(elapsed, 3),
                })
        return pd.DataFrame(rows)


if __name__ == "__main__":
    import sys
    from pathlib import Path

    df = RaceConditionBenchmark().run().sort_values("time_s")

    if "--output" in sys.argv:
        output = Path(sys.argv[sys.argv.index("--output") + 1])
        df.to_json(output)
    else:
        print(df.to_string(index=False))
