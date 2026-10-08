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
- **`a` is *total* acceleration (speed change + turning), not ds/dt.** It tracks sqrt(a_tan² + a_cen²) at r = 0.99 (combine)
  and 0.87 (game) vs ~0.6 for |ds/dt|. At a cut it mixes braking and turning, and it agrees less well in game data,
  so compute a_tan = ds/dt and a_cen = s·dθ/dt from x/y/s/dir the same way in both sources; don't compare vendor `a` across them.
- **Combine `dis` is not the frame displacement** (median 0.33 in 3-cone to 0.90 in the 40, so it can't be rescaled).
  Use `s` or x/y for distance in combine data. Game `dis` is fine.
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

- Link (1) compares the same mechanic in two places. Game features rest on ~160 scored breaks per qualified WR
  vs ~17 combine cuts, but game breaks vary with the play call and defense, so both sides are only moderately
  reliable (0.55–0.71 in games, 0.55–0.63 at the combine; Phase 2).
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
The provided `a` is unsigned *total* acceleration in both sources, so signed (tangential) acceleration has to come from smoothed speed,
and turn load (v²/r = s·dθ/dt) from smoothed `dir` or x/y.

### Phase 1 results (Oct 8; full tables in `reports/01_combine_features.md`)

The cut detector (`src/cuts.py`) finds the drill's known breaks: exactly two ~176° reversals in 94% of shuttles,
none on straight go routes, and the route's first break goes the expected way in 91–100% of reps, counting reps with no detected cut as misses (which also
confirms the left/right sign). In the shuttle and 3-cone, tracking-derived braking correlates −0.58 and −0.53
with the official times, so the metrics measure real agility.

Each metric is z-scored within its slot (same break of the same drill across players), adjusted for the break's
turn angle so breaks are compared at equal sharpness, then averaged per player.
Split-half reliability across a WR's ~9 drills / ~17 cuts:

| Signal | Reliability | Decision |
|---|---|---|
| Speed into the break (`entry_speed`) | 0.63 | **pre-registered** |
| Speed retention (apex ÷ entry) | 0.55 | **pre-registered** |
| Peak lateral acceleration (turn load) | 0.59 | **pre-registered** |
| Peak braking | 0.33 | secondary only (r = −0.81 with retention) |
| Distance used to slow down | 0.21 | dropped |
| Re-acceleration (speed regained in 0.5 s) | ≈ 0 | dropped (the catch follows the break in drills) |
| Left/right asymmetry (any metric) | ≤ 0.18 | dropped (each route breaks a fixed way, so drill and side are confounded) |
| Rep consistency (any metric) | ≤ 0.41 | dropped (almost no repeat reps of a drill) |

The three pre-registered signals are nearly independent of the 40, the 10-yard split and size (|r| ≤ 0.16).
They are not straight-line speed again, which is what the baseline-beating claim needs. Retention and turn load
do track the 3-cone time (r ≈ −0.48, among the ~33 WRs who ran it), as change-of-direction measures should.

*Scoring change (Phase 2):* the turn-angle adjustment was added while building the game features, in both sources.
It was chosen on reliability alone, before any combine–game or outcome comparison, and raised the three
pre-registered features' combine reliability from 0.51–0.58 to 0.55–0.63.

### Phase 2 results (Oct 8; full tables in `reports/02_game_features.md`)

The Phase 1 detector runs unchanged on the 30,955 regular-season WR routes with a throw (87% of 35,427), keeping
breaks whose apex falls between the snap and the throw. For WRs lined up wide, the first break goes the way the
route is designed: toward the middle for slants (98%), ins (88%), posts (85%) and crosses (82%), toward the sideline
for outs (91%), corners (92%) and flats (79%). Many routes have no break before the throw (70% of posts, for example):
the ball often goes out first, often to another receiver; posts and crosses round off below 30°; hitches stop rather
than turn.

Game breaks are slotted by route type × direction × order and adjusted, within slot, for turn angle, break depth,
alignment (wide/slot), man vs zone coverage and pre-snap motion. Split-half reliability across games for the 63
qualified WRs (≥ 100 routes; median 159 scored breaks):

| Game feature | Reliability |
|---|---|
| Speed into the break | 0.71 |
| Speed retention | 0.55 |
| Peak lateral acceleration | 0.60 |
| Peak braking (secondary) | 0.61 |

That is well short of what §3 originally assumed ("thousands of game reps, so stable"): game breaks vary with the
play call and the defense far more than combine reps do. (Left − right turn load is 0.43 reliable in games; exploratory only.)

| Outcome (per route) | Reliability | Role |
|---|---|---|
| Separation over expected (SOE): vs. routes of the same type, coverage family and alignment | 0.73 | **pre-registered primary** |
| Targets per route run | 0.84 | **pre-registered secondary** |
| Yards per route run | 0.81 | **pre-registered secondary** |
| EPA on targets per route | 0.57 | exploratory |
| Catch rate | 0.65 | exploratory |
| YAC over expected | 0.17 | dropped (noise) |

SOE is primary because it is the outcome a route break should move directly, and it already conditions on play
design and coverage (raw separation is 3.5 yd vs zone, 2.1 yd vs man). Qualified WRs by class: 29 (2023), 19 (2024),
15 (2025). Rookie-season versions of every feature and outcome exist for class-balanced checks.

**Power caveat for Phase 3.** With ~63 qualified WRs, a correlation needs |r| ≥ 0.35 to be detected (80% power,
α = 0.05). Measurement noise on both ends shrinks true correlations: Link (1) by ~0.55–0.67× (combine × game
reliability), Link (2) by ~0.63–0.72× (game feature × SOE). So only true correlations of roughly 0.5–0.65 (Link 1)
and 0.5–0.55 (Link 2) are likely to show up. Phase 3 should report disattenuated estimates with intervals and model
breaks directly (partial pooling) rather than lean on significance tests of player means.

## 6. Phases and timeline (13 weeks)

| # | Phase | Dates | Done when |
|---|---|---|---|
| 0 | Setup + data audit | Oct 7 – Oct 18 | ✅ Oct 8: data loads; counts per position/class/drill; REG-season filter verified (`notebooks/00_audit.py`) |
| 1 | Combine features | Oct 19 – Nov 8 | ✅ Oct 8: cut detector validated on combine drills; feature table per player (`notebooks/01_combine_features.py`) |
| 2 | Game features + outcomes | Nov 9 – Nov 22 | ✅ Oct 8: same cut metrics on in-game routes (snap → pass forward, slots = `route_ran` × direction); outcome table per player (`notebooks/02_game_features.py`) |
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
