"""Build the public Kaggle notebook from this repo's code.

The notebook writes `src/` and `notebooks/` exactly as they are in the repo, runs the six
steps on Kaggle's copy of the competition data, and shows the writeup's figures and tables.
Rebuild it after any code change so the Kaggle copy never drifts from the tested code.

Run: `python scripts/build_kaggle_notebook.py` (writes kaggle/cut-that-doesnt-travel.ipynb)
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "kaggle" / "cut-that-doesnt-travel.ipynb"
STEPS = ["00_audit", "01_combine_features", "02_game_features", "03_models", "03b_sensitivity", "04_writeup"]
FIGURES = [
    ("04_signature.png", "Figure 1. One receiver's combine speed-out vs the same receiver's game out-breaks."),
    ("03_tests.png", "Figure 2. The three pre-registered tests."),
    ("04_within.png", "Figure 3. Within each receiver, separation rises with the break against man coverage."),
    ("04_ceiling.png", "Figure 4. The measurement ceiling vs the observed combine–game correlation, with the "
                       "positive control."),
    ("04_card.png", "Figure 5. In-season scouting card."),
    ("04_stabilize.png", "Figure 6. How fast in-game break metrics settle."),
]


def md(text: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": text.strip("\n").splitlines(keepends=True)}


def code(text: str) -> dict:
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
            "source": text.strip("\n").splitlines(keepends=True)}


def writefile(rel: str) -> dict:
    body = (ROOT / rel).read_text(encoding="utf-8")
    if not body.strip():  # %%writefile rejects an empty cell
        return code(f'Path("{rel}").write_text({body!r})')
    return code(f"%%writefile {rel}\n{body}")


cells = [
    md("""
# The cut that doesn't travel: what Combine route drills miss about NFL route breaks

**NFL Big Data Bowl 2027 · code notebook for the writeup.**

Do the ways a wide receiver breaks in the Combine route drills carry into how they break in regular-season games,
and into how open they get? This notebook reproduces every number and figure in the writeup from the competition
data. It writes the project's code (identical to the repository), then runs six steps:

| Step | What it does |
|---|---|
| `00_audit` | Data checks: regular-season filter, counts, what `a` and `dis` measure |
| `01_combine_features` | One cut detector on the WR position drills; combine cut features per player |
| `02_game_features` | The same detector on 30,499 regular-season routes; game features and separation over expected |
| `03_models` | The pre-registered tests (combine → game, game break → separation, combine → separation) |
| `03b_sensitivity` | Checks added after them: matched combine cuts, a positive control, play context, man vs zone, what a yard of separation is worth |
| `04_writeup` | The writeup's figures and the numbers they cite |

Every step ends with hard checks (`assert`), so a finished run means every check passed. Runtime is about
15–20 minutes on a Kaggle CPU session.
"""),
    md("## Setup"),
    code("""
import os
import subprocess
import sys
from pathlib import Path

# Find the competition CSVs: Kaggle's input folder, or BDB_RAW_DIR when run elsewhere.
candidates = [Path(os.environ["BDB_RAW_DIR"])] if "BDB_RAW_DIR" in os.environ else []
candidates += sorted(p.parent for p in Path("/kaggle/input").rglob("players.csv")) if Path("/kaggle/input").exists() else []
RAW = next((c for c in candidates if (c / "players.csv").exists()), None)
assert RAW is not None, "Attach the NFL Big Data Bowl 2027 competition data to this notebook."
os.environ["BDB_RAW_DIR"] = str(RAW)
print("competition data:", RAW)

try:
    import duckdb  # noqa: F401
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "duckdb>=1.1"], check=True)

PROJECT = Path("bdb").resolve()
for d in ["src", "notebooks", "reports/figures", "logs"]:
    (PROJECT / d).mkdir(parents=True, exist_ok=True)
os.chdir(PROJECT)
print("project folder:", PROJECT)
"""),
    md("""
## Project code

The cells below write the project's modules and step scripts exactly as they are in the repository. They are long;
the results follow in the next sections.
"""),
    *[writefile(f"src/{p.name}") for p in sorted((ROOT / "src").glob("*.py"))],
    *[writefile(f"notebooks/{s}.py") for s in STEPS],
    md("## Run the six steps"),
    code("""
def run(step: str) -> None:
    r = subprocess.run([sys.executable, f"notebooks/{step}.py"], capture_output=True, text=True)
    (PROJECT / "logs" / f"{step}.log").write_text(r.stdout + r.stderr)
    if r.returncode != 0:
        raise RuntimeError(f"{step} failed:\\n{r.stderr[-4000:]}")
    print(f"{step}: {r.stdout.strip().splitlines()[-1]}")


for step in """ + repr(STEPS) + """:
    run(step)
"""),
    md("""
## Results

The pre-registered tests from `reports/03_models.md`, the checks added after them from `reports/03b_sensitivity.md`,
then the writeup's figures. The full reports for every step are in `bdb/reports/`.
"""),
    code("""
from IPython.display import Image, Markdown, display

report = (PROJECT / "reports" / "03_models.md").read_text()
start = report.index("## Test 1")
end = report.index("## Secondary analyses")
display(Markdown(report[start:end]))
"""),
    md("### Added after the pre-registered tests (not pre-registered)"),
    code("""
checks = (PROJECT / "reports" / "03b_sensitivity.md").read_text()
display(Markdown(checks[checks.index("## Tests 1 and 3 on matched combine cuts"):]))
"""),
    *[c for name, caption in FIGURES
      for c in (md(f"*{caption}*"), code(f'display(Image(filename=str(PROJECT / "reports" / "figures" / "{name}")))'))],
]

nb = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}
for i, c in enumerate(nb["cells"]):
    c["id"] = f"cell-{i:03d}"
OUT.parent.mkdir(exist_ok=True)
OUT.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"wrote {OUT.relative_to(ROOT)} ({len(cells)} cells)")
