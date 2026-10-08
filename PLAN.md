# NFL Big Data Bowl 2027 — Project Plan

Theme: link 10 Hz Combine tracking to **regular-season** NFL performance.
Deadline: **January 6, 2027, 11:59 PM UTC** (started Oct 6, 2026). Results Jan 26, 2027.
Finalists present at the 2027 NFL Scouting Combine (+$10k grand prize).

## 1. What the judges score

| Component | Weight | What it asks |
|---|---|---|
| Football | 30% | Usable by teams week-to-week? Handles football complexity? Unique idea? |
| Data Science | 30% | Correct? Claims backed by data? Models fit the data? Innovative? |
| Writeup | 20% | Well written, easy to follow, motivation clearly defined |
| Data Viz | 20% | Accessible, accurate, innovative charts/tables |

Pass/fail gates (fail = not scored):
1. Explicitly links Combine sensor tracking to **regular-season** game performance.
2. Readable markdown writeup, embedded visuals, attached **public** Kaggle Notebook.

Limits: ≤ 2,000 words, fewer than 10 tables/figures. Code goes in an appendix or linked notebook.

Organizers explicitly encourage a narrow focus: one movement trait, one position group, or one drill.

## 2. The data (9 CSVs, ~2.3 GB, 510 rookies, draft classes 2023–2025)

| File | Grain | Key use |
|---|---|---|
| `players.csv` | player | position, draft class, draft pick (null = UDFA) |
| `combine_results.csv` | player | standard testing (40, 10-yd split, 3-cone, shuttle, …) + NGS scores → **baseline** |
| `combine_tracking.csv` | event × frame (10 Hz) | x, y, s, a, dis, dir per drill attempt. **No body orientation (`o`)** |
| `player_career_successes.csv` | player | snaps, games active/started, All-Pro, Pro Bowl |
| `player_play.csv` | player × play | separation, pressure, get-off, EPA, coverage, routes |
| `games.csv` | game | season, `season_type` (REG/POST), week |
| `game_tracking_20XX.csv` | player × play × frame | x, y, s, a, o, dir, event tags. **Cohort players only** |

Drill types: `FORTY_YARD_DASH`, `THREE_CONE_DRILL`, `SHORT_SHUTTLE`, `SKILL_DRILLS_{WR,DB,OL,DL,TE}`.

Data traps to handle in Phase 0:
- Game tracking includes **preseason** (e.g. game_id `20240809xx`) and **playoffs**. Filter to `season_type == REG` and IDs present in `games.csv`.
- Game tracking covers **only the 510 rookies**, not opponents or teammates. Matchup metrics can't be recomputed from tracking; use `player_play` NGS fields (e.g. `separation_at_pass_forward`).
- 2025 class has **one season** of NFL data; 2023 class has three. Normalize outcomes per snap/route, and compare within draft class.
- Snaps depend on draft slot (teams play high picks). Always control for draft pick.
- Small N: ~510 players total, split across ~15 positions.

### Phase 0 findings (Oct 8; full tables in `reports/00_audit.md`)

- **Effective WR N is ~60, not 106.** 82 WRs have any REG snap; 62 have 100+ REG routes, 38 have 300+.
  2025 class median is 27 routes. Shrinkage (§7) is essential, and the 2025 holdout fold will be thin.
- **Shuttle / 3-cone tracking covers only ~25% of WRs** (29 and 24 of 107). `SKILL_DRILLS_WR` covers all 107
  (15 named route drills, ~1,500 reps), so WR cut signals must come from position drills.
  Standard 3-cone/shuttle *times* are also missing for ~65% of WRs, so the baseline uses 40, split, vertical, broad, size.
- **`a` is unsigned magnitude in both combine and game tracking.** Deceleration must be derived from smoothed speed.
  `dir` uses the same convention in both (clockwise from +y), so cut geometry transfers directly.
- **REG filter verified:** PRE is 14–20% and POST 3–5% of game frames. All game IDs are in `games.csv`.
  Use the `game_tracking_reg` / `player_play_reg` views in `src/data.py`.
- `separation_at_pass_forward` is recorded on ~85% of WR routes (not just targets), so it works as a per-route outcome.
- Combine reps are keyed by `event_id` (a few share `(nfl_id, drill_name, attempt)`). Combine data is clean 10 Hz with no gaps.
- No QBs, effectively no RBs, and no off-ball LBs in the cohort.

## 3. Core idea: the "translation chain" (recommended)

Instead of jumping straight from Combine numbers to career stats (small N, noisy), link them in two steps:

```
Combine cut mechanics  ──(1)──>  same mechanics in NFL games  ──(2)──>  NFL outcome
(WR position drills)             (each route break / cut                 (separation,
                                  in game tracking)                       EPA, targets)
```

- Link (1) has thousands of game reps per player, so player-level game metrics are stable.
- Link (2) shows the mechanic matters on the field.
- Headline: **which Combine movement traits carry over into games, and which don't**, beyond what the stopwatch time already says.

Every claim must beat the **baseline model**: draft pick + 40, split, vertical, broad jump, height, and weight.

## 4. Recommended focus: wide receivers (route breaks → separation)

Why WRs:
- Richest outcome: `separation_at_pass_forward`, targets, `route_ran`, YAC, EPA per route.
- Direct drill match: `SKILL_DRILLS_WR` (route drills, gauntlet); shuttle and 3-cone tracking cover only ~25% of WRs.
- Listed first in the organizers' examples.

Stretch (only if WR finishes early): DBs (`SKILL_DRILLS_DB` backpedal/transition → ball-arrival closing speed).

## 5. Candidate Combine signals (from x, y, s, a, dir at 10 Hz)

| Signal | Definition sketch |
|---|---|
| Decel into break | peak deceleration and distance used to slow down before a cut |
| Speed retention | exit speed ÷ entry speed through each cut |
| Re-acceleration | time from cut apex back to 80% of entry speed |
| Turn load | v²/r lateral demand at the cut (from `dir` change and speed) |
| Left/right asymmetry | same metrics split by cut direction |
| Rep consistency | variation across attempts of the same drill |

Smooth x/y before differentiating (e.g. Savitzky–Golay); 10 Hz derivatives are noisy.
The provided `a` is unsigned in both sources, so signed (tangential) acceleration has to come from smoothed speed.

### Phase 1 results (Oct 8; full tables in `reports/01_combine_features.md`)

The cut detector (`src/cuts.py`) finds the drill's known breaks: exactly two ~176° reversals in 94% of shuttles,
none on straight go routes, and the route's first break goes the expected way in 95–100% of reps (which also
confirms the left/right sign). In the shuttle and 3-cone, tracking-derived braking correlates −0.50 and −0.44
with the official times, so the metrics measure real agility.

Each metric is z-scored within its slot (same break of the same drill across players), then averaged per player.
Split-half reliability across a WR's ~9 drills / ~17 cuts:

| Signal | Reliability | Decision |
|---|---|---|
| Speed into the break (`entry_speed`) | 0.58 | **pre-registered** |
| Speed retention (apex ÷ entry) | 0.51 | **pre-registered** |
| Peak lateral acceleration (turn load) | 0.53 | **pre-registered** |
| Peak braking | 0.40 | secondary only (r = −0.89 with retention) |
| Distance used to slow down | 0.23 | dropped |
| Re-acceleration (speed regained in 0.5 s) | 0.11 | dropped (the catch follows the break in drills) |
| Left/right asymmetry (any metric) | ≤ 0.08 | dropped (each route breaks a fixed way, so drill and side are confounded) |
| Rep consistency (any metric) | 0.00–0.38 | dropped (almost no repeat reps of a drill) |

The three pre-registered signals are nearly independent of the 40, the 10-yard split and size (|r| ≤ 0.2).
They are not straight-line speed again, which is what the baseline-beating claim needs.

**Power caveat for Phase 3.** With ~60 WRs, a correlation needs |r| ≥ 0.36 to be detected (80% power, α = 0.05).
Combine-side reliability of ~0.55 shrinks any true correlation by ~0.7–0.75×, so only true |r| ≳ 0.5 are likely
to show up. Shrinkage and the game-side rep counts (thousands of routes) matter more than adding signals.

## 6. Phases and timeline (13 weeks)

| # | Phase | Dates | Done when |
|---|---|---|---|
| 0 | Setup + data audit | Oct 7 – Oct 18 | ✅ Oct 8: data loads; counts per position/class/drill; REG-season filter verified (`notebooks/00_audit.py`) |
| 1 | Combine features | Oct 19 – Nov 8 | ✅ Oct 8: cut detector validated on combine drills; feature table per player (`notebooks/01_combine_features.py`) |
| 2 | Game features + outcomes | Nov 9 – Nov 22 | Same cut metrics computed on in-game routes (snap → pass forward, slots = `route_ran` × direction); outcome table per player |
| 3 | Modeling | Nov 23 – Dec 13 | Leave-one-draft-class-out results vs. baseline; uncertainty intervals |
| 4 | Writeup + viz | Dec 14 – Jan 2 | Draft notebook public; ≤ 2,000 words; < 10 figures |
| 5 | Buffer + submit | Jan 3 – Jan 6 | Submitted by Jan 5 (one day early) |

## 7. Modeling rules

- Validate by holding out one draft class at a time.
- Mixed / hierarchical models with partial pooling (players with few reps shrink toward the group mean).
- Prefer interpretable models (regularized regression, GAMs) over black boxes.
- Pre-register a short list of signals; correct for multiple testing; bootstrap intervals.
- Report the gain over the baseline, not raw correlations.

## 8. Writeup plan (< 10 figures)

1. One signature figure: a player's Combine cut vs. the same player's in-game cuts, overlaid.
2. Translation table: which Combine traits carry into games (and which don't).
3. Outcome chart: game cut metric vs. separation, with uncertainty.
4. Scouting card: how a team would use the metric on draft day.
5. Hidden-gem / bust case studies (2–3 players).

## 9. Repo layout

```
data/raw/        # CSVs from scripts/download_data.sh (gitignored)
data/parquet/    # Parquet copies built by src/data.py (gitignored)
data/features/   # derived cut / feature tables (gitignored)
notebooks/       # 00_audit … 04_writeup
src/             # data, cuts, features, outcomes, models, viz
tests/           # python -m pytest
reports/figures/
```

## 10. Open decisions

- Track: Open or University (University = undergraduates only).
- Focus: WR (recommended) vs. another group.
- Team: solo or team.
- ~~Data access~~: resolved. `scripts/download_data.sh` works with a `KGAT_` token in `KAGGLE_API_TOKEN` or `KAGGLE_API_KEY`.
