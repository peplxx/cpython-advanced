"""Run lab benchmarks across CPython versions."""

from pathlib import Path

import nox

nox.options.default_venv_backend = "uv"

PYTHON_VERSIONS = ["3.12", "3.13", "3.13t", "3.14", "3.14t"]
RESULTS_DIR = Path("results")


@nox.session(python=PYTHON_VERSIONS)
def benchmark(session: nox.Session) -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    output = RESULTS_DIR / f"benchmark_{session.python}.json"
    session.install("pandas")
    session.run("python", "-m", "lab.benchmark", "--output", str(output), *session.posargs, env={"PYTHONPATH": ".."})


@nox.session(python=PYTHON_VERSIONS)
def strace(session: nox.Session) -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    output = RESULTS_DIR / f"strace_{session.python}.json"
    session.install("pandas")
    session.run("python", "-m", "lab.strace_bench", "--output", str(output), *session.posargs, env={"PYTHONPATH": ".."})


@nox.session(python=PYTHON_VERSIONS[0])
def tests(session: nox.Session) -> None:
    session.install("pytest")
    session.run("pytest", "lab/tests", *session.posargs, env={"PYTHONPATH": "."})
