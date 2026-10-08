"""Game routes: one window per route, and the same cut detector the combine uses.

A route's window runs from the snap to the throw (`pass_forward`). Breaks are
kept only if their apex falls inside it: after the throw the receiver is
playing the ball, not running the route. Kinematics are computed on a slightly
wider window (0.5 s before the snap, 1 s after the throw) so a break near either
edge still has the frames its turn angle and exit metrics need.

Only routes with a throw are used, because separation (the main outcome) is
measured at the throw.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.cuts import cuts_for_reps

KEY = ["game_id", "play_id", "nfl_id"]
PRE_SNAP_S = 0.5
POST_THROW_S = 1.0

CENTER_Y = 53.3 / 2
# Beyond this distance (yd) from the field's center line, a player is clearly on one side of the ball
# (the ball is always between the hashes, 3.1 yd either side of center).
WIDE_MARGIN = 9.0

# Play-design context each game break is adjusted for within its slot, on top of the turn angle:
# how deep the break is, where the receiver lined up, the coverage family, and pre-snap motion.
COVARIATES = ("turn_deg", "depth", "depth_sq", "slot_alignment", "other_alignment", "man_coverage", "in_motion")

INSIDE_ROUTES = ("SLANT", "IN", "POST", "CROSS")    # main break goes toward the middle of the field
OUTSIDE_ROUTES = ("OUT", "CORNER", "FLAT")          # main break goes toward the sideline


def routes(con, combine_position: str = "WR") -> pd.DataFrame:
    """One row per regular-season route (with one snap and a throw) run by players of a combine position."""
    return con.sql(f"""
        WITH r AS (
            SELECT pp.game_id, pp.play_id, pp.nfl_id, pp.season, pp.route_ran, pp.play_direction,
                   pp.lined_up_position, pp.in_motion_at_ball_snap, pp.team_coverage_man_zone
            FROM player_play_reg pp JOIN combine_results c USING (nfl_id)
            WHERE c.combine_position = '{combine_position}' AND pp.route_ran IS NOT NULL),
        e AS (
            SELECT t.game_id, t.play_id, t.nfl_id,
                   min(t.time) FILTER (WHERE t.event = 'ball_snap') AS snap,
                   min(t.time) FILTER (WHERE t.event = 'pass_forward') AS pass_forward,
                   count(*) FILTER (WHERE t.event = 'ball_snap') AS n_snaps
            FROM game_tracking_reg t JOIN r USING (game_id, play_id, nfl_id) GROUP BY ALL),
        s AS (
            SELECT t.game_id, t.play_id, t.nfl_id, t.x AS x_snap, t.y AS y_snap
            FROM game_tracking_reg t JOIN e USING (game_id, play_id, nfl_id) WHERE t.time = e.snap)
        SELECT r.*, e.snap, e.pass_forward, s.x_snap, s.y_snap,
               (epoch_ms(e.pass_forward) - epoch_ms(e.snap)) / 1000.0 AS throw_s
        FROM r JOIN e USING (game_id, play_id, nfl_id) JOIN s USING (game_id, play_id, nfl_id)
        WHERE e.pass_forward > e.snap AND e.n_snaps = 1  -- a handful of routes carry two snap events; which is real is ambiguous
        ORDER BY r.game_id, r.play_id, r.nfl_id
    """).df()


def route_frames(con, rts: pd.DataFrame) -> pd.DataFrame:
    """Tracking frames from PRE_SNAP_S before the snap to POST_THROW_S after the throw, for each route."""
    con.register("_routes", rts[KEY + ["snap", "pass_forward"]])
    try:
        return con.sql(f"""
            SELECT t.game_id, t.play_id, t.nfl_id, t.time, t.x, t.y, t.s
            FROM game_tracking_reg t JOIN _routes r USING (game_id, play_id, nfl_id)
            WHERE t.time BETWEEN r.snap - INTERVAL {int(PRE_SNAP_S * 1000)} MILLISECOND
                             AND r.pass_forward + INTERVAL {int(POST_THROW_S * 1000)} MILLISECOND
            ORDER BY t.game_id, t.play_id, t.nfl_id, t.time
        """).df()
    finally:
        con.unregister("_routes")


def inside_direction(play_direction: pd.Series, y_snap: pd.Series) -> pd.Series:
    """Turn direction ("L"/"R") that points toward the middle of the field; NaN near the center.

    Moving downfield toward +x, a player at high y is on the offense's left, so turning
    toward the middle is a right turn; moving toward -x the sides swap.
    """
    toward_right = (play_direction == "right") == (y_snap > CENTER_Y)
    out = pd.Series(np.where(toward_right, "R", "L"), index=y_snap.index, dtype=object)
    return out.where((y_snap - CENTER_Y).abs() > WIDE_MARGIN)


def route_cuts(frames: pd.DataFrame, rts: pd.DataFrame) -> pd.DataFrame:
    """Cuts whose apex falls between the snap and the throw, with route context.

    Adds `route_id` (one id per route), `t_apex` (s after the snap), `inside`
    (1.0 if the break went toward the middle of the field, 0.0 if toward the
    sideline, NaN when the player lined up too close to the center to tell),
    `depth` (yd downfield of the snap position at the apex) and the numeric
    COVARIATES.
    """
    cuts = cuts_for_reps(frames, KEY).merge(rts, on=KEY)
    cuts["t_apex"] = (cuts["apex_time"] - cuts["snap"]).dt.total_seconds()
    cuts = cuts[(cuts["t_apex"] >= 0) & (cuts["t_apex"] <= cuts["throw_s"] + 1e-6)].reset_index(drop=True)
    cuts["route_id"] = cuts[KEY].astype(str).agg("_".join, axis=1)
    ins = inside_direction(cuts["play_direction"], cuts["y_snap"])
    cuts["inside"] = (cuts["turn_dir"] == ins).astype(float).where(ins.notna())
    at_apex = cuts[KEY + ["apex_time"]].merge(
        frames[KEY + ["time", "x"]].rename(columns={"time": "apex_time"}), on=KEY + ["apex_time"], how="left")
    downfield = np.where(cuts["play_direction"] == "right", 1.0, -1.0)
    cuts["depth"] = (at_apex["x"].to_numpy() - cuts["x_snap"].to_numpy()) * downfield
    cuts["depth_sq"] = cuts["depth"] ** 2
    cuts["slot_alignment"] = (cuts["lined_up_position"] == "SLOT_WR").astype(float)
    cuts["other_alignment"] = (~cuts["lined_up_position"].isin(["WR", "SLOT_WR"])).astype(float)
    cuts["man_coverage"] = (cuts["team_coverage_man_zone"] == "MAN_COVERAGE").astype(float)
    cuts["in_motion"] = cuts["in_motion_at_ball_snap"].fillna(False).astype(float)
    return cuts
