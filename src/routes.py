"""In-game WR routes: route windows, cuts with the Phase 1 detector, and player cut features.

The detector in `src.cuts` runs unchanged on game routes, so combine and game
cuts get identical processing. What changes is the scoring, because game breaks
vary more than drill breaks:

- A route window runs from the snap to 1 s after the throw. Cuts count if their
  apex is no later than 0.5 s after the throw: on timing routes the QB often
  releases just before the break. Cuts less than 1 yd past the receiver's snap
  position are release moves at the line, not route breaks, and are dropped.
- Break side is relative to the field: `in` turns toward the middle of the field
  (a proxy for the ball, which isn't tracked), `out` toward the sideline. Combine
  route drills are run from a fixed side, so there turn direction already means
  the same thing.
- Slot = route_ran x break side. Within a slot, game breaks still differ in depth
  and angle (a 5-yd quick out vs a 12-yd deep out), which drives entry speed and
  speed retention. So each metric is regressed on depth and turn angle (with
  squares) within its slot and the standardized residual is the cut's score. In
  the combine each slot is one fixed drill break, so plain z-scores do the same job.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src import cuts as C
from src.data import PARQUET

FIELD_CENTER_Y = 160 / 3 / 2   # yd; the field is 53.3 yd wide
TAIL = 1.0                     # s of tracking kept after the throw, so late breaks are fully measured
MAX_AFTER_THROW = 0.5          # s: latest apex that still counts as part of the route
MIN_DEPTH = 1.0                # yd past the snap position; shallower cuts are release moves
EXCLUDED_ROUTES = ("SCREEN",)  # designed separation, no route break
MIN_CUTS_PER_SLOT = 20
METRICS = ("entry_speed", "speed_retention", "peak_lat_accel", "peak_decel")
KEY = ["game_id", "play_id", "nfl_id"]


def _tracking_files() -> str:
    return ", ".join(f"'{PARQUET}/game_tracking_{y}.parquet'" for y in (2023, 2024, 2025))


def wr_routes(con) -> pd.DataFrame:
    """One row per WR route in a regular-season play (penalty-nullified plays dropped).

    Snap and throw times come from the receiver's own tracking event tags.
    `ttt` (time to throw, s) is null when the play has no pass_forward tag (sacks, scrambles).
    """
    return con.sql(f"""
        WITH ev AS (
            SELECT game_id, play_id, nfl_id,
                   min(time) FILTER (WHERE event = 'ball_snap') AS t_snap,
                   min(time) FILTER (WHERE event = 'pass_forward') AS t_pass
            FROM read_parquet([{_tracking_files()}])
            WHERE event IN ('ball_snap', 'pass_forward')
              AND nfl_id IN (SELECT nfl_id FROM players WHERE nfl_position = 'WR')
            GROUP BY ALL)
        SELECT pp.game_id, pp.play_id, pp.nfl_id, pp.season, pp.week, pp.route_ran,
               coalesce(pp.team_coverage_man_zone, 'UNKNOWN') AS coverage, pp.play_direction,
               pp.pass_result, pp.target, pp.rec_yards, pp.yards_after_catch, pp.expected_yards_after_catch,
               pp.expected_points_added, pp.separation_at_pass_forward AS separation,
               ev.t_snap, ev.t_pass, (epoch_ms(ev.t_pass) - epoch_ms(ev.t_snap)) / 1000 AS ttt
        FROM player_play_reg pp
        JOIN players p USING (nfl_id)
        LEFT JOIN ev USING (game_id, play_id, nfl_id)
        WHERE p.nfl_position = 'WR' AND pp.route_ran IS NOT NULL AND pp.play_nullified_by_penalty = 'N'
        ORDER BY game_id, play_id, nfl_id
    """).df()


def route_frames(con, routes: pd.DataFrame) -> pd.DataFrame:
    """Tracking frames from the snap to TAIL seconds after the throw, for routes with both tags."""
    win = routes.loc[routes.t_snap.notna() & routes.t_pass.notna(), [*KEY, "t_snap", "t_pass"]]
    con.register("route_windows", win)
    try:
        return con.sql(f"""
            SELECT t.game_id, t.play_id, t.nfl_id, t.time, t.x, t.y, t.s
            FROM read_parquet([{_tracking_files()}]) t JOIN route_windows w USING (game_id, play_id, nfl_id)
            WHERE t.time BETWEEN w.t_snap AND w.t_pass + INTERVAL {int(TAIL * 1000)} MILLISECOND
            ORDER BY t.game_id, t.play_id, t.nfl_id, t.time
        """).df()
    finally:
        con.unregister("route_windows")


def break_side(turn_dir: str, vx_in: float, y_apex: float) -> str:
    """`in` if the turn rotates the incoming velocity toward the middle of the field, else `out`.

    Rotating velocity (vx, vy) counter-clockwise (a left turn) moves it toward the
    point (x, FIELD_CENTER_Y) when the cross product vx * (FIELD_CENTER_Y - y) is positive.
    """
    toward_middle_is_left = vx_in * (FIELD_CENTER_Y - y_apex) > 0
    return "in" if (turn_dir == "L") == toward_middle_is_left else "out"


def route_cuts(frames: pd.DataFrame, routes: pd.DataFrame) -> pd.DataFrame:
    """Every cut the Phase 1 detector finds in each route window, with route context.

    Adds `break_side`, `depth` (yd downfield from the snap position), `t_after_snap`,
    `t_after_throw` (s; negative = before the throw) and `kept` (counts as a route break).
    """
    info = {tuple(k): v for k, v in zip(routes[KEY].to_numpy(),
                                        routes[["route_ran", "play_direction", "ttt"]].itertuples(index=False))}
    f = frames.sort_values([*KEY, "time"])
    keys = f[KEY].to_numpy()
    starts = np.flatnonzero(np.r_[True, (keys[1:] != keys[:-1]).any(axis=1)])
    ends = np.r_[starts[1:], len(f)]
    xs, ys = f["x"].to_numpy(float), f["y"].to_numpy(float)
    out = []
    for s0, s1 in zip(starts, ends):
        if s1 - s0 <= 2 * C.HALF_WINDOW:
            continue
        key = tuple(keys[s0])
        x, y = xs[s0:s1], ys[s0:s1]
        k = C.kinematics(x, y)
        route, direction, ttt = info[key]
        downfield = 1.0 if direction == "right" else -1.0
        for i, c in enumerate(C.detect_cuts(k)):
            a = c["apex_frame"]
            b = max(a - C.HALF_WINDOW, 0)  # the incoming velocity the turn angle starts from
            out.append({
                **dict(zip(KEY, key)), "route_ran": route, "cut_idx": i, "n_frames": int(s1 - s0), **c,
                "break_side": break_side(c["turn_dir"], k["vx"][b], y[a]),
                "depth": downfield * (x[a] - x[0]),
                "t_after_snap": a * C.DT,
                "t_after_throw": a * C.DT - ttt,
            })
    cuts = pd.DataFrame(out)
    cuts["kept"] = (
        (cuts.t_after_throw <= MAX_AFTER_THROW + 1e-9)
        & (cuts.depth >= MIN_DEPTH)
        & ~cuts.route_ran.isin(EXCLUDED_ROUTES)
    )
    return cuts


def slot_z_adjusted(cuts: pd.DataFrame, metrics=METRICS) -> pd.DataFrame:
    """Add `slot` (route|side) and `<metric>_z`: within-slot standardized residual after depth and angle.

    Slots with fewer than MIN_CUTS_PER_SLOT cuts are dropped.
    """
    c = cuts.copy()
    c["slot"] = c["route_ran"] + "|" + c["break_side"]
    c = c[c.groupby("slot")["slot"].transform("size") >= MIN_CUTS_PER_SLOT].copy()
    for m in metrics:
        c[f"{m}_z"] = np.nan
    for _, g in c.groupby("slot"):
        X = np.column_stack([np.ones(len(g)), g.depth, g.depth ** 2, g.turn_deg, g.turn_deg ** 2])
        for m in metrics:
            yv = g[m].to_numpy(float)
            ok = np.isfinite(yv)
            beta, *_ = np.linalg.lstsq(X[ok], yv[ok], rcond=None)
            res = yv - X @ beta
            c.loc[g.index, f"{m}_z"] = res / np.nanstd(res[ok], ddof=1)
    return c


def main_breaks(zcuts: pd.DataFrame) -> pd.DataFrame:
    """Each route's main designed break: the first cut on the route's expected side (HITCH: first cut).

    Used as a sensitivity check; GO, FLAT, WHEEL and ANGLE routes have no single designed break and are left out.
    """
    expect = {"SLANT": "in", "IN": "in", "POST": "in", "CROSS": "in", "OUT": "out", "CORNER": "out"}
    z = zcuts.sort_values([*KEY, "apex_frame"])
    on_side = z.route_ran.map(expect) == z.break_side
    return pd.concat([z[on_side], z[z.route_ran == "HITCH"]]).groupby(KEY).head(1)


def player_features(zcuts: pd.DataFrame, prefix: str = "game", metrics=METRICS) -> pd.DataFrame:
    """One row per player: mean score per metric over all kept cuts, plus counts."""
    g = zcuts.groupby("nfl_id")
    feats = pd.DataFrame({
        f"{prefix}_n_cuts": g.size(),
        f"{prefix}_n_routes": zcuts.drop_duplicates(KEY).groupby("nfl_id").size(),
    })
    for m in metrics:
        feats[f"{prefix}_{m}"] = g[f"{m}_z"].mean()
    return feats
