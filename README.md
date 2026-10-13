# The cut that doesn't travel

**NFL Big Data Bowl 2027.** What Combine route drills miss about NFL route breaks.

Does the way a wide receiver breaks in the Combine route drills carry into how they break in regular-season games,
and into how open they get? One cut detector is applied unchanged to the 10 Hz Combine drill tracking and to 30,499
regular-season routes. Every claim is tested against what teams already have: draft slot and the standard tests.

- **The combine cut doesn't travel.** None of the three pre-registered traits (speed into the break, speed
  retention, peak lateral acceleration) predicts the same trait in games, or separation, beyond the baseline.
  Held out one draft class at a time, adding them lowers out-of-sample R² for separation from 0.41 to 0.38.
  Rebuilding the combine scores from each drill's designed break alone leaves them null.
- **The pipeline does find transfer where it should.** As a positive control, top speed in the tracked 40 predicts
  peak speed on go routes (r = +0.39, 95% CI +0.14 to +0.59).
- **The game cut matters, mostly against man coverage.** Within a receiver, each SD of speed into the break is worth
  +0.11 yd of separation over expected (95% CI +0.07 to +0.15), and +0.09 with play context controlled. Split by
  coverage, it is +0.19 yd against man and +0.07 against zone.
- **In football terms:** against man, a receiver's fastest fifth of breaks come out 0.65 yd more open than their
  slowest, worth roughly 4 points of completion rate.

The Phase 3 tests were pre-registered. The matched combine cuts, the positive control, the play-context controls and
the man–zone split were added afterwards and are reported in `reports/03b_sensitivity.md`.

![The three pre-registered tests](reports/figures/03_tests.png)

## Read

- [`writeup/writeup.md`](writeup/writeup.md): the competition writeup.
- [`PLAN.md`](PLAN.md): the project plan. Its Phase 3 analysis plan was pre-registered in commit `6d770a1`, before any
  combine-to-game link was computed.
- [`reports/`](reports): full tables for every step (`00_audit.md` … `04_numbers.md`, with `03b_sensitivity.md`)
  and all figures.
- [`kaggle/`](kaggle): the public Kaggle notebook, generated from this repository.

## Reproduce

Tested on Python 3.13. Needs about 2.3 GB of disk for the competition data.

```bash
pip install -r requirements.txt

# Competition data into data/raw/. Accept the competition rules on kaggle.com first, then set
# KAGGLE_API_TOKEN (or KAGGLE_USERNAME and KAGGLE_KEY).
bash scripts/download_data.sh

# The six steps, in order. Each ends with hard checks and writes its report to reports/.
python notebooks/00_audit.py
python notebooks/01_combine_features.py
python notebooks/02_game_features.py
python notebooks/03_models.py
python notebooks/03b_sensitivity.py
python notebooks/04_writeup.py

python -m pytest
```

The six steps take about 6–7 minutes on a 4-core machine. To read the data from somewhere other than `data/raw/`,
set `BDB_RAW_DIR` to that folder. The step scripts are in jupytext percent format, so they also open as notebooks.

The Kaggle notebook writes `src/` and `notebooks/` exactly as they are here, then runs the same six steps. After any
code change, rebuild it with `python scripts/build_kaggle_notebook.py`.

## Layout

```
src/           data loading, cut detection, route breaks, outcomes, reliability and model helpers
notebooks/     00_audit … 04_writeup, with 03b_sensitivity: the six steps
reports/       one report per step, and figures/
writeup/       the competition writeup
kaggle/        the generated Kaggle notebook and publishing steps
scripts/       data download and the Kaggle notebook builder
tests/         python -m pytest
data/          competition CSVs and derived tables (not committed)
```
