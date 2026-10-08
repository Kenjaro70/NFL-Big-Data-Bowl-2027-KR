"""Regular-season WR outcomes, per route and per player.

Separation at the throw depends heavily on things the receiver doesn't control:
man vs zone coverage (about 2.0 vs 3.4 yd on average), the route, and how long
the QB holds the ball. Separation over expected (`soe`) subtracts the average
separation of cohort WRs on the same route, against the same coverage, with a
similar time to throw. Screens are left out of separation outcomes: they are
designed to be open.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.routes import EXCLUDED_ROUTES

TTT_BINS = [0, 2.0, 2.5, 3.0, 3.5, np.inf]
TTT_LABELS = ["<2.0", "2.0-2.5", "2.5-3.0", "3.0-3.5", ">=3.5"]
MIN_CELL = 30  # routes; smaller cells fall back to a coarser cell


def separation_routes(routes: pd.DataFrame) -> pd.DataFrame:
    """Routes with a separation value and a throw time, with expected separation and `soe` added.

    Expected separation is the mean over (route, coverage, time-to-throw bin) when that cell has
    at least MIN_CELL routes, else over (route, coverage), else over route.
    """
    r = routes[routes.separation.notna() & routes.ttt.notna() & ~routes.route_ran.isin(EXCLUDED_ROUTES)].copy()
    r["ttt_bin"] = pd.cut(r.ttt, TTT_BINS, labels=TTT_LABELS, right=False).astype(str)
    expected = pd.Series(np.nan, index=r.index)
    for cell in (["route_ran", "coverage", "ttt_bin"], ["route_ran", "coverage"], ["route_ran"]):
        g = r.groupby(cell)["separation"]
        fill = expected.isna() & (g.transform("size") >= MIN_CELL)
        expected[fill] = g.transform("mean")[fill]
    r["expected_separation"] = expected.fillna(r.separation.mean())
    r["soe"] = r.separation - r.expected_separation
    return r


def explained_variance(sep_routes: pd.DataFrame) -> float:
    """Share of route-level separation variance explained by the expected-separation cells."""
    resid = sep_routes.separation - sep_routes.expected_separation
    return float(1 - resid.var() / sep_routes.separation.var())


def route_outcomes(routes: pd.DataFrame) -> pd.DataFrame:
    """Per-route outcome columns whose player mean is the player outcome.

    `target` (0/1) and `yards` average to target rate and yards per route run, and
    `epa_route` (EPA when targeted, else 0) to EPA per route run. `catch` is only set
    on targets and `yac_oe` only on catches, so their means are per target / per catch.
    """
    targeted = routes.target.fillna(False).astype(bool)
    caught = targeted & (routes.pass_result == "C")
    return routes.assign(
        target=targeted.astype(float),
        yards=routes.rec_yards.fillna(0),
        epa_route=routes.expected_points_added.where(targeted, 0.0),
        catch=caught.astype(float).where(targeted),
        yac_oe=(routes.yards_after_catch - routes.expected_yards_after_catch).where(caught),
    )


def player_outcomes(routes: pd.DataFrame, sep_routes: pd.DataFrame, prefix: str = "") -> pd.DataFrame:
    """One row per WR: usage, production and separation over the given routes."""
    r = route_outcomes(routes)
    g = r.groupby("nfl_id")
    targeted = r[r.target == 1]
    out = pd.DataFrame({
        "routes": g.size(),
        "games": g["game_id"].nunique(),
        "targets": g["target"].sum(),
        "rec_yards": g["rec_yards"].sum(min_count=1),
    })
    out["target_rate"] = out.targets / out.routes
    out["yprr"] = g["yards"].mean()
    out["epa_per_route"] = g["epa_route"].mean()
    out["epa_per_target"] = targeted.groupby("nfl_id")["expected_points_added"].mean()
    out["catch_rate"] = g["catch"].mean()
    out["yac_oe"] = g["yac_oe"].mean()
    s = sep_routes.groupby("nfl_id")
    out["sep_routes"] = s.size()
    out["separation"] = s["separation"].mean()
    out["soe"] = s["soe"].mean()
    out["man_share"] = s["coverage"].apply(lambda c: (c == "MAN_COVERAGE").mean())
    return out.add_prefix(prefix)


def career(con) -> pd.DataFrame:
    """Career usage and honors (player_career_successes), indexed by nfl_id."""
    return con.sql("SELECT * FROM player_career_successes").df().set_index("nfl_id")
