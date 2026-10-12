# The cut that doesn't travel: what Combine route drills miss about NFL route breaks

## 1. Why cutting, and why the Combine

A receiver gets open at the break. The stem sells one route, the plant converts speed into a turn, and the defender
either stays in phase or doesn't. Scouts watch that break closely, and the Combine's position drills are the only
time a draft class's receivers run the same breaks, on the same field, under the same tracking.

The 2027 Big Data Bowl adds 10 Hz tracking to those drills, so the break can finally be measured rather than eyeballed.
This entry asks one narrow question for wide receivers: **does the way a receiver breaks in the Combine route drills
carry into how they break in regular-season games, and into how open they get?** Every claim has to beat what teams
already have: draft slot and the standard tests (40, 10-yard split, vertical, broad jump, height, weight).

The short answer is no. The combine cut doesn't travel, at least not in a way 16 drill cuts per player can detect.
But the same mechanics measured in games do matter: within a receiver, routes with a faster, cleaner break are more
open at the throw.

## 2. Measuring a cut the same way twice

Everything rests on one cut detector applied unchanged to both data sources. Positions are smoothed (Savitzky–Golay,
0.7 s), and a cut is a turn of at least 30° between the velocity half a second before and half a second after a frame.
Its apex is the slowest point of the turn. The detector finds the drills' known geometry (two reversals in 94% of
short-shuttle reps) and the routes' known direction: in games, the first break goes the way the route is drawn on
80–96% of slants, ins, posts, crossers, outs and corners.

From each cut come three pre-registered signals: **speed into the break**, **speed retention** (apex speed ÷ entry
speed) and **peak lateral acceleration** (how hard the receiver turns). Each is scored against the same break run by
other players (the same drill break at the Combine; the same route type and side in games, adjusted for depth and turn
angle). Peak braking is a secondary signal.

The Combine side uses the 106 receivers with tracked WR position drills (about 1,500 reps of 15 route drills). The
game side uses 30,499 regular-season routes with a snap and a throw, from which 13,895 route breaks qualify. Turns in
the first 1.5 s are left out: they are mostly release moves and receivers in motion, and their numbers track role
rather than cutting. The outcome is **separation over expected (SOE)**: separation at the throw minus the average for
the same route type, coverage and time to throw. Inference uses the 62 receivers with at least 100 regular-season
routes.

![Jordan Addison's combine speed-out vs 141 game out-breaks](../reports/figures/04_signature.png)

*Figure 1. One receiver, one break, two settings. Jordan Addison (the qualified receiver with the most game out-breaks
among those who ran the combine speed-out) is at 3.9 yd/s 1.5 s before the drill's apex; the median game out-break is
at 4.8 yd/s. The paths match; the situations don't.*

## 3. Finding 1: the combine cut doesn't travel

All tests were pre-registered and committed before any combine-to-game link was computed. Two questions come first:
does each combine trait predict the same trait in games, and does it predict separation, beyond draft slot and the
standard tests?

| Combine trait | Reliability: combine / games | Same trait in games, beyond baseline (β, 95% CI) | Separation over expected, beyond baseline (yd per SD, 95% CI) |
|---|---|---|---|
| Speed into the break | 0.58 / 0.77 | +0.15 [−0.08, +0.37] | +0.00 [−0.06, +0.06] |
| Speed retention | 0.51 / 0.51 | +0.10 [−0.15, +0.37] | +0.04 [−0.02, +0.10] |
| Peak lateral acceleration | 0.53 / 0.59 | +0.02 [−0.24, +0.28] | +0.00 [−0.05, +0.06] |

*Table 1. The translation table: none of the three traits carries over. Reliability is split-half, Spearman–Brown
corrected (across drills at the Combine, across games in the NFL). Intervals are from 2,000 player bootstrap resamples;
none of the six tests clears its Holm-corrected threshold.*

None of the three carries over. Raw correlations between a receiver's combine trait and the same trait in games are
0.17, 0.08 and −0.02. None predicts separation beyond the baseline either. Held out one draft class at a time, a model
of separation with the baseline alone reaches an out-of-sample R² of 0.41; adding all three combine cut signals lowers
it to 0.38.

This is "not detected", not "ruled out". With 62 receivers, the intervals still allow a moderate effect for speed into
the break (β up to 0.37). What the data rule out is a strong one.

## 4. Finding 2: the game cut matters

The second pre-registered question is whether the mechanic matters on the field at all. If faster, cleaner breaks
didn't buy separation in games, the combine result would be uninteresting.

The test compares each receiver's routes with each other: on routes where a receiver breaks better than their own
average, are they more open at the throw? Comparing a receiver to themself removes role, quarterback and scheme. It
uses 8,371 routes with a break before the throw.

![The three pre-registered tests](../reports/figures/03_tests.png)

*Figure 2. The three pre-registered tests side by side. Filled markers clear the Holm correction.*

![Within-receiver separation vs break quality](../reports/figures/04_within.png)

*Figure 3. Within each receiver, separation rises with the break. Points are fifths of each receiver's own routes.*

Two of the three in-game signals matter. Each standard deviation of speed into the break is worth **+0.11 yd** of
separation over expected (95% CI +0.07 to +0.15, Holm p < 0.001). Each standard deviation of speed retention is worth
**+0.08 yd** (+0.03 to +0.13, Holm p = 0.009). Lateral acceleration shows no detectable effect (+0.03, interval crossing zero).
Braking harder goes with less separation (−0.12 yd per SD, a secondary signal).

These are small per route, because one route's separation is noisy (SD 1.91 yd). Across a receiver's own routes, the
top fifth by entry speed are 0.30 yd more open than the bottom fifth, about a fifth of the gap between man and zone
coverage (about 1.4 yd). Both effects keep a positive sign in each of the three draft classes.

## 5. Why the transfer fails

The following explanations are hypotheses that fit the numbers, not tested results.

**Noise caps what can be seen, but doesn't explain it all.** A receiver runs about 16 measurable combine cuts against
153 game breaks. Given both reliabilities, the largest correlation measurement noise allows between a combine trait and
its game version is 0.67 for speed into the break, 0.51 for retention and 0.56 for lateral acceleration. The observed
values sit far below those ceilings, and for speed into the break even the top of the interval (0.41) is well short of
0.67. Noise alone can't account for the gap: the drill and the game appear to measure partly different things.

![Measurement ceiling vs observed correlation](../reports/figures/04_ceiling.png)

*Figure 4. Grey bars: the largest correlation the two reliabilities allow. Blue: what was observed, with 95% intervals.*

**The situations differ.** Drills are unopposed and scripted. In Figure 1, Addison was still accelerating into the
drill's break (3.9 yd/s 1.5 s before the apex, against 4.8 in the median game out-break). In games, the break depends on leverage,
coverage, the stem and the quarterback's timing. A single combine cut is more repeatable than a single game break
(split-half reliability per cut of about 0.06–0.08 against 0.01–0.02), but it is repeatable at something else: running
a drill well.

## 6. How a team would use it

**On draft day:** don't read route-drill tracking as a preview of game break quality beyond the stopwatch. Addison is a
clean example (Figure 5). By combine percentile among the 62 qualified receivers, their speed into the break was the
lowest of the group (0th). In 658 game breaks it sits at the median (50th), and their separation over expected at the
47th.

![Scouting card](../reports/figures/04_card.png)

*Figure 5. In-season scouting card: combine drill percentile (squares) vs game percentile (circles).*

**In season:** the game version of the metric is what's worth tracking. Speed into the break settles quickly. Its
reliability is 0.53 after a receiver's first 25 routes and about 0.7 by 200–300 routes. Retention and lateral
acceleration need about 400. At the median of about 19 routes a game for a regular, speed into the break can be trusted
after roughly 11–16 games, and retention and lateral acceleration after about 21, more than a season.

![Stabilization by route count](../reports/figures/04_stabilize.png)

*Figure 6. Split-half reliability of each game metric over a receiver's first N routes.*

**For coaching:** the within-receiver effect is about the routes a receiver runs well against the ones they don't. A
staff can flag routes where entry speed drops below a receiver's own norm: on average, those routes come out less
open.

## 7. Limits and what's next

- **Sample.** 62 qualified receivers limits player-level tests to large effects. The 2025 class has a single season.
- **Association.** The within-receiver effect is not proof of cause. Unmeasured details such as defender leverage or
  the coverage call within a family could move both break speed and separation.
- **The outcome.** SOE adjusts for route, coverage and time to throw but not alignment. In this sample, heavier
  receivers are less open (an exploratory finding, probably role).
- **Scope.** Rounded breaks under 30° and turns in the first 1.5 s are not counted, which removes many slant breaks.
  Without ball tracking, "inside" means toward the middle of the field.

Next steps: extend the same detector to defensive backs (backpedal and transition drills against ball-arrival
closing speed), and test whether a team's in-season break metrics, once stable, predict the following season's
separation.

## Appendix

Code, pre-registration (PLAN.md, commit `6d770a1`) and every table behind these numbers: the linked public notebook
and repository (`notebooks/00_audit.py` … `04_writeup.py`; `reports/00`–`04`). Statistics: OLS with HC3 or
player-clustered errors, player bootstrap intervals, Holm correction within each test family, ridge regression
validated by leaving out one draft class at a time.
