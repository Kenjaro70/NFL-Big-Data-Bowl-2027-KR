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

- Link (1) compares the same mechanic in two places. Game features rest on ~150 route breaks per qualified WR
  vs ~17 combine cuts, but game breaks vary with the play call, so game reliability is moderate (0.40–0.77; Phase 2).
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

### Phase 2 results (Oct 8; full tables in `reports/02_game_features.md`)

The Phase 1 detector runs unchanged on 30,499 regular-season WR route windows (snap to 1 s after the throw).
Where a route has a known shape, the first break goes that way: inside on 80–94% of slants, ins, posts and
crossers, outside on 95–96% of outs and corners. Rounded breaks stay under the 30° threshold, so the share of
routes with a counted break ranges from 27% (crossers) to 76% (outs).

Design choices, made on game data only (no outcome or combine linkage looked at):
- Breaks up to 0.5 s after the throw count: on timing routes the QB throws first, and 90% of those late breaks
  still go the route's way. Turns less than 1 yd past the snap spot are release moves and don't count. No screens.
- Breaks also need their whole 1.5 s entry window after the snap. Earlier cuts are mostly release moves and
  motion men turning upfield (31% in motion vs 6% later); their entry speed and braking are measured partly on the
  stance or the motion, so they track role, not cutting. Cost: 45% of cuts detected on slants are that early.
- Break side is `in` / `out` relative to the middle of the field, not left / right, so a release move on a slant
  can't share a slot with other receivers' main breaks.
- Slot = route × side, and within a slot each metric is regressed on depth and turn angle. Game breaks of one route
  type vary in geometry: plain slot z-scores correlate 0.56 with depth (entry speed) and −0.68 with angle (retention).
- Outcome = separation over expected (SOE): separation at the throw minus the cohort mean for the same route,
  coverage and time-to-throw bin. Coverage matters most (about 2.0 yd vs man, 3.4 vs zone).
- Reliability is measured on the 62 qualified WRs (≥ 100 regular-season routes). Counting every WR with ≥ 6 games
  instead adds 11 WRs with 11–95 routes, whose noisy averages cut SOE reliability from 0.72 to 0.44.

| Signal | Combine reliability | Game reliability | Smallest detectable true r, combine → game (62 WRs) |
|---|---|---|---|
| Speed into the break | 0.58 | 0.77 | 0.52 |
| Speed retention | 0.51 | 0.51 | 0.68 |
| Peak lateral acceleration | 0.53 | 0.59 | 0.62 |
| Peak braking (secondary) | 0.40 | 0.40 | 0.87 |

Outcome reliability across games (62 qualified WRs): target rate 0.84, yards per route run 0.81, raw separation
0.76, SOE 0.72, catch rate 0.70, EPA on targets per route 0.59, YAC over expected 0.16 (noise). SOE stays the
Phase 3 outcome; the others are for reference. Every game feature and outcome also exists for the rookie season
alone (median ~70 breaks per WR), so draft classes with one, two or three seasons can be compared on equal terms.

**Implication for Phase 3.** Player-to-player tests can only find large effects: speed into the break needs a
true r ≥ 0.52 (combine → game) and every combine → SOE test needs ≥ 0.54–0.58. A route-level model of link (2), with
each break's scores vs SOE on the same route and player random effects (~14k breaks), has no such ceiling. It should
carry the "the mechanic matters on the field" claim, with the player-level translation table as the second piece.

### Phase 3 analysis plan (pre-registered Oct 8, committed before any combine–game or outcome link was computed)

**Sample.** The 62 qualified WRs (≥ 100 regular-season routes), all with combine WR-drill features. Features,
outcomes and scoring exactly as merged in Phase 2; nothing is re-tuned after this point.

**Baseline (B).** log(draft overall pick) with UDFAs set to pick 260 plus a UDFA indicator, 40, 10-yd split,
vertical, broad jump, height, weight. Missing tests (5–8 WRs each) are filled with the training-sample median.
All predictors are standardized.

**Signals.** Primary: speed into the break, speed retention, peak lateral acceleration (pre-registered in Phase 1).
Secondary, reported but not corrected: peak braking. Each signal is tested on its own (one model per signal).

**Test 1, link (1): does the combine trait carry into games?** Per signal m: OLS of game_m on B + combine_m. Statistic:
the combine_m coefficient (reported as a partial r), two-sided p from HC3 standard errors, 95% CI from 2,000
player bootstrap resamples. Also reported, not tested: raw r and r disattenuated by both reliabilities.

**Test 2, link (2): does the mechanic matter on the field?** Unit: one route with a separation value and at least one
kept break with its apex at or before the throw (breaks after the throw can't change separation at the throw);
~8,400 routes. Predictor x = the route's mean break score for m. Model: SOE = a + b_w·(x − x̄_player) + b_b·x̄_player.
Statistic: b_w, the within-player effect (on routes where a WR cuts better than their own average, are they more open?),
which removes player-level confounds such as role, QB and scheme. Two-sided p from player-clustered (CR1) standard
errors; 95% CI from 2,000 player-cluster bootstrap resamples. b_b is reported. Units: yd of SOE per 1 SD of break score.

**Test 3, headline: does the combine trait predict separation beyond the baseline?** Per signal m: OLS of player SOE on
B + combine_m; same statistic, p and CI as Test 1. Out-of-sample check, leave one draft class out (train on two classes,
predict the third, pool the three held-out folds): ridge regression (penalty by generalized cross-validation inside the
training folds) with B only vs B + all three primary signals; report out-of-sample R² for each and the gain.

**Multiple testing.** Holm correction within each test family (3 primary signals), α = 0.05.
Verdicts: "carries over" / "matters" = Holm-adjusted p < 0.05; "suggestive" = unadjusted p < 0.05 only; otherwise
"no evidence", always with the CI and Phase 2's smallest detectable effect next to it.

**Secondary (reported, not corrected).** Peak braking in all three tests; target rate and yards per route run as
outcomes in Test 3; Test 3 on rookie-season SOE (WRs with ≥ 100 rookie routes) so the three classes are on equal
footing; Test 2 with all kept breaks instead of pre-throw breaks only; b_w per draft class (does the sign hold?).

### Phase 3 results (Oct 8; full tables in `reports/03_models.md`)

Every pre-registered test ran as written; nothing was re-tuned. 62 qualified WRs; 8,371 routes for Test 2.

| Signal | Test 1: combine → game trait (β, SD per SD) | Test 2: break score → SOE, within player (yd per SD) | Test 3: combine trait → SOE (yd per SD) |
|---|---|---|---|
| Speed into the break | +0.15 [−0.08, +0.37], no evidence | **+0.11 [+0.07, +0.15], matters** (Holm p < 0.001) | +0.00 [−0.06, +0.06], no evidence |
| Speed retention | +0.10 [−0.15, +0.37], no evidence | **+0.08 [+0.03, +0.13], matters** (Holm p = 0.009) | +0.04 [−0.02, +0.10], no evidence |
| Peak lateral acceleration | +0.02 [−0.24, +0.28], no evidence | +0.03 [−0.02, +0.07], no evidence | +0.00 [−0.05, +0.06], no evidence |
| Peak braking (secondary) | −0.07 [−0.38, +0.21] | −0.12 [−0.17, −0.06], p < 0.001 | −0.02 [−0.07, +0.03] |

- **Link (1) not detected.** No combine cut trait predicts the same trait in games beyond the baseline (raw r −0.02
  to 0.17). The intervals still allow moderate effects (β up to ~0.37), so this is "not detected", not "ruled out".
- **Link (2) holds within players.** On routes where a WR enters the break faster, or keeps more of their speed through
  it, than their own norm, they are more open at the throw: +0.11 and +0.08 yd per SD (route-level SOE has an SD of
  1.91 yd). More braking goes with less separation (−0.12, secondary). Entry speed and retention keep a positive sign
  in all three draft classes (secondary).
- **Headline (Test 3) not detected.** No combine cut trait predicts SOE beyond the baseline. Leaving one draft class
  out, adding the three signals lowers out-of-sample R² from 0.41 (baseline) to 0.38. The baseline's R² comes mostly
  from weight (heavier WRs are less open, −0.14 yd per SD; exploratory, probably role).

**Implication for Phase 4.** The combine route drills measure the mechanic but don't predict it on Sundays, and they
don't add to the stopwatch for separation. The mechanic itself matters in games: break entry speed and speed retention
are worth about 0.1 yd of separation per SD within a receiver. The writeup's framing (lead with the null transfer, or
with the in-game effect) is the open decision for Phase 4.

## 6. Phases and timeline (13 weeks)

| # | Phase | Dates | Done when |
|---|---|---|---|
| 0 | Setup + data audit | Oct 7 – Oct 18 | ✅ Oct 8: data loads; counts per position/class/drill; REG-season filter verified (`notebooks/00_audit.py`) |
| 1 | Combine features | Oct 19 – Nov 8 | ✅ Oct 8: cut detector validated on combine drills; feature table per player (`notebooks/01_combine_features.py`) |
| 2 | Game features + outcomes | Nov 9 – Nov 22 | ✅ Oct 8: detector validated on game routes; game cut features and outcome table per WR (`notebooks/02_game_features.py`) |
| 3 | Modeling | Nov 23 – Dec 13 | ✅ Oct 8: pre-registered tests with leave-one-draft-class-out results vs. baseline and bootstrap intervals (`notebooks/03_models.py`) |
| 4 | Writeup + viz | Dec 14 – Jan 2 | Draft notebook public; ≤ 2,000 words; < 10 figures |
| 5 | Buffer + submit | Jan 3 – Jan 6 | Submitted by Jan 5 (one day early) |

## 7. Modeling rules

- Validate by holding out one draft class at a time.
- Mixed / hierarchical models with partial pooling (players with few reps shrink toward the group mean).
- Prefer interpretable models (regularized regression, GAMs) over black boxes.
- Pre-register a short list of signals; correct for multiple testing; bootstrap intervals.
- Report the gain over the baseline, not raw correlations.

## 8. Writeup plan (< 10 figures)

**Framing (decided Oct 8): lead with the combine finding.** Working title: *"The cut that doesn't travel: what
Combine route drills miss about NFL route breaks."* The headline answers the competition's question directly
(Combine tracking → regular-season performance): the combine cut traits don't carry over, while the same
mechanics measured in games do matter for separation.

| # | Section | Words | Figure / table |
|---|---|---|---|
| 1 | Why cutting, why the Combine | ~200 | — |
| 2 | Measuring a cut the same way twice (drills and games, one detector) | ~350 | **F1** signature: one WR's combine break vs the same WR's game breaks, speed through the turn |
| 3 | Finding 1: the combine cut doesn't travel | ~350 | **T1** translation table (Test 1 + Test 3, with CIs and the smallest detectable effect) |
| 4 | Finding 2: the game cut matters | ~350 | **F2** within-player separation vs break entry speed and retention; **F3** the three tests side by side |
| 5 | Why the transfer fails (labeled as hypotheses) | ~250 | **F4** reliability: ~17 combine cuts vs ~150 game breaks per WR |
| 6 | How a team would use it | ~250 | **F5** in-season scouting card; **F6** how many routes before a WR's break metrics are trustworthy |
| 7 | Limits and what's next | ~150 | — |
| | Appendix: method, pre-registration, code | — | linked public Kaggle notebook |

About 1,900 words and 7 figures/tables, under the 2,000 / < 10 limits. F6 (stabilization by route count) and the
F2 binned view are new descriptive work for Phase 4; no new hypothesis tests.

## 9. Repo layout

```
data/raw/        # CSVs from scripts/download_data.sh (gitignored)
data/parquet/    # Parquet copies built by src/data.py (gitignored)
data/features/   # derived cut / feature tables (gitignored)
notebooks/       # 00_audit … 04_writeup
src/             # data, cuts, features, routes, outcomes, stats, models, viz
tests/           # python -m pytest
reports/figures/
```

## 10. Open decisions

- Track: Open or University (University = undergraduates only).
- ~~Focus~~: resolved. Wide receivers (Phases 1–3).
- Team: solo or team.
- ~~Data access~~: resolved. `scripts/download_data.sh` works with a `KGAT_` token in `KAGGLE_API_TOKEN` or `KAGGLE_API_KEY`.
