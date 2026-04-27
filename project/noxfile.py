import nox
from pathlib import Path

nox.options.default_venv_backend = "uv"

PYTHON_VERSIONS = ["3.13", "3.13t", "3.14", "3.14t"]
RESULTS_DIR = Path("results")


@nox.session(python=PYTHON_VERSIONS)
def experiments(session: nox.Session) -> None:
    experiment = session.posargs[0] if session.posargs else "race_condition"
    output = RESULTS_DIR / f"{experiment}_{session.python}.json"
    RESULTS_DIR.mkdir(exist_ok=True)
    session.install("pandas", "plotly")
    session.run("python", f"experiments/{experiment}.py", "--output", str(output))
