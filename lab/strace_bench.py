"""Count futex syscalls per bounded-buffer scenario via `strace -c`.

Reruns benchmark.py under strace for each (impl, producers, consumers, capacity)
configuration and parses futex call/error counts from `strace -c` output.

Linux only.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


SCENARIOS = [
    {"producers": 2, "consumers": 2, "capacity": 10},
    {"producers": 4, "consumers": 4, "capacity": 10},
    {"producers": 1, "consumers": 1, "capacity": 1},
    {"producers": 4, "consumers": 4, "capacity": 100},
]

FUTEX_LINE = re.compile(
    r"^\s*(?P<pct>[\d.]+)\s+(?P<seconds>[\d.]+)\s+\d+\s+(?P<calls>\d+)\s+(?:(?P<errors>\d+)\s+)?futex\s*$"
)


def _strace_one(impl: str, producers: int, consumers: int, capacity: int, total: int) -> dict:
    cmd = [
        "strace", "-f", "-c", "-e", "trace=futex",
        sys.executable, "-c",
        (
            "from lab.benchmark import _run_once;"
            f"from lab.bounded_buffer import IMPLS;"
            f"_run_once(IMPLS[{impl!r}], {producers}, {consumers}, {capacity}, {total})"
        ),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    futex_calls = 0
    futex_errors = 0
    for line in proc.stderr.splitlines():
        m = FUTEX_LINE.match(line)
        if m:
            futex_calls  = int(m.group("calls"))
            futex_errors = int(m.group("errors") or 0)
            break
    return {
        "impl":         impl,
        "producers":    producers,
        "consumers":    consumers,
        "capacity":     capacity,
        "items":        total,
        "futex_calls":  futex_calls,
        "futex_errors": futex_errors,
    }


def run(total: int, scenarios=SCENARIOS) -> list[dict]:
    rows = []
    for impl in ("condition", "semaphore"):
        for s in scenarios:
            rows.append(_strace_one(impl, total=total, **s))
    return rows


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--total",  type=int, default=200_000, help="items per scenario (default 200_000)")
    parser.add_argument("--output", type=Path,                 help="write JSON instead of printing")
    return parser.parse_args()


if __name__ == "__main__":
    if sys.platform != "linux":
        sys.exit("strace_bench requires Linux")

    args = _parse_args()
    rows = run(total=args.total)

    py = f"{sys.version_info.major}.{sys.version_info.minor}"
    if sys.flags.gil == 0:
        py += "t"
    for r in rows:
        r["python"] = py

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(rows, indent=2))
    else:
        for r in rows:
            print(r)
