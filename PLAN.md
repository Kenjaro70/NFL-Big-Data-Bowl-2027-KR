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

## 3. Core idea: the "translation chain" (recommended)

Instead of jumping straight from Combine numbers to career stats (small N, noisy), link them in two steps:

```
Combine cut mechanics  ──(1)──>  same mechanics in NFL games  ──(2)──>  NFL outcome
(shuttle, 3-cone,               (each route break / cut                 (separation,
 position drills)                in game tracking)                       EPA, targets)
```

- Link (1) has thousands of game reps per player, so player-level game metrics are stable.
- Link (2) shows the mechanic matters on the field.
- Headline: **which Combine movement traits carry over into games, and which don't**, beyond what the stopwatch time already says.

Every claim must beat the **baseline model**: draft pick + standard combine results (40, split, 3-cone, shuttle, height, weight).

## 4. Recommended focus: wide receivers (route breaks → separation)

Why WRs:
- Richest outcome: `separation_at_pass_forward`, targets, `route_ran`, YAC, EPA per route.
- Direct drill match: `SKILL_DRILLS_WR` (route drills, gauntlet), short shuttle, 3-cone.
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

## 6. Phases and timeline (13 weeks)

| # | Phase | Dates | Done when |
|---|---|---|---|
| 0 | Setup + data audit | Oct 7 – Oct 18 | Data loads; counts per position/class/drill; REG-season filter verified |
| 1 | Combine features | Oct 19 – Nov 8 | Cut detector works on combine drills; feature table per player |
| 2 | Game features + outcomes | Nov 9 – Nov 22 | Same cut metrics computed on in-game routes; outcome table per player |
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
data/            # raw CSVs (gitignored)
notebooks/       # 00_audit … 04_writeup
src/             # io, smoothing, cuts, features, outcomes, models, viz
reports/figures/
```

## 10. Open decisions

- Track: Open or University (University = undergraduates only).
- Focus: WR (recommended) vs. another group.
- Team: solo or team.
- Data access: Kaggle API token needed to download the 2.3 GB of data into this environment.
