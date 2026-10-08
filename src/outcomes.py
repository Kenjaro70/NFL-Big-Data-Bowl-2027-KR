"""NFL outcomes for route runners, per route and per player.

Every regular-season route counts (dropbacks that end in a sack or scramble
included), so per-route rates use the standard denominators. Separation only
exists on routes with a throw.

Separation over expected (SOE) compares each route with the average separation
of cohort routes of the same type, against the same coverage family (man/zone),
from the same alignment (wide/slot): man coverage alone costs ~1.4 yd, and a
screen is open by design. Cells with < MIN_CELL routes fall back to route x
coverage, then route type, then coverage, then the cohort average.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

MIN_CELL = 30

# outcome -> (numerator column, denominator column) on the route table; player value = sum(num) / sum(den)
OUTCOMES = {
    "separation": ("separation", "has_separation"),
    "soe": ("soe", "has_separation"),
    "tprr": ("target", "route"),
    "yprr": ("rec_yards", "route"),
    "epa_per_route": ("epa_target", "route"),
    "catch_rate": ("catch", "target"),
    "yacoe": ("yacoe", "has_yacoe"),
}
OUTCOME_LABELS = {
    "separation": "separation at the throw (yd)",
    "soe": "separation over expected (yd)",
    "tprr": "targets per route run",
    "yprr": "receiving yards per route run",
    "epa_per_route": "EPA on targets, per route run",
    "catch_rate": "catches per target",
    "yacoe": "yards after catch over expected, per catch",
}


def route_outcomes(con, combine_position: str = "WR") -> pd.DataFrame:
    """One row per regular-season route with outcome columns and expected separation."""
    r = con.sql(f"""
        SELECT pp.game_id, pp.play_id, pp.nfl_id, pp.season, p.draft_year, pp.route_ran,
               CASE pp.lined_up_position WHEN 'WR' THEN 'wide' WHEN 'SLOT_WR' THEN 'slot' ELSE 'other' END AS alignment,
               coalesce(pp.team_coverage_man_zone, 'UNKNOWN') AS coverage,
               pp.separation_at_pass_forward AS separation,
               coalesce(pp.target, FALSE)::INT AS target,
               (coalesce(pp.target, FALSE) AND pp.pass_result = 'C')::INT AS catch,
               CASE WHEN pp.target AND pp.pass_result = 'C' THEN coalesce(pp.rec_yards, 0) ELSE 0 END AS rec_yards,
               CASE WHEN pp.target THEN pp.expected_points_added ELSE 0 END AS epa_target,
               CASE WHEN pp.target AND pp.pass_result = 'C'
                    THEN pp.yards_after_catch - pp.expected_yards_after_catch END AS yacoe
        FROM player_play_reg pp JOIN combine_results c USING (nfl_id) JOIN players p USING (nfl_id)
        WHERE c.combine_position = '{combine_position}' AND pp.route_ran IS NOT NULL
        ORDER BY pp.game_id, pp.play_id, pp.nfl_id
    """).df()
    r["route"] = 1
    r["has_separation"] = r["separation"].notna().astype(int)
    r["has_yacoe"] = r["yacoe"].notna().astype(int)
    r["epa_target"] = r["epa_target"].fillna(0.0)
    r["expected_separation"] = expected_separation(r)
    r["soe"] = r["separation"] - r["expected_separation"]
    return r


def expected_separation(r: pd.DataFrame) -> pd.Series:
    """Mean cohort separation for the route's cell (finest level with >= MIN_CELL routes)."""
    has = r[r["separation"].notna()]
    exp = pd.Series(np.nan, index=r.index)
    for cols in (["route_ran", "coverage", "alignment"], ["route_ran", "coverage"], ["route_ran"], ["coverage"]):
        cell = has.groupby(cols)["separation"].agg(["mean", "size"])
        cell = cell[cell["size"] >= MIN_CELL]["mean"]
        fill = r[cols].merge(cell.rename("m").reset_index(), on=cols, how="left")["m"].to_numpy()
        exp = exp.fillna(pd.Series(fill, index=r.index))
    return exp.fillna(has["separation"].mean())


def player_outcomes(r: pd.DataFrame, prefix: str = "") -> pd.DataFrame:
    """Per-player outcome rates (ratio of sums over routes), plus route / target / game counts."""
    g = r.groupby("nfl_id")
    out = pd.DataFrame({
        f"{prefix}routes": g["route"].sum(),
        f"{prefix}targets": g["target"].sum(),
        f"{prefix}games": g["game_id"].nunique(),
    })
    sums = g[sorted({c for pair in OUTCOMES.values() for c in pair})].sum(min_count=1)
    for name, (num, den) in OUTCOMES.items():
        out[f"{prefix}{name}"] = sums[num] / sums[den].replace(0, np.nan)
    return out


def outcome_reliability(r: pd.DataFrame, n_iter: int = 200, seed: int = 0) -> pd.DataFrame:
    """Spearman-Brown corrected split-half reliability of each player outcome, splitting each player's games."""
    rng = np.random.default_rng(seed)
    games = r[["nfl_id", "game_id"]].drop_duplicates().sort_values(["nfl_id", "game_id"])
    stats = {k: [] for k in OUTCOMES}
    for _ in range(n_iter):
        half = games.assign(h=rng.random(len(games)))
        half["h"] = half.groupby("nfl_id")["h"].rank(method="first") % 2
        rr = r.merge(half, on=["nfl_id", "game_id"])
        a, b = player_outcomes(rr[rr.h == 0]), player_outcomes(rr[rr.h == 1])
        for k in stats:
            c = a[k].corr(b[k])
            stats[k].append(2 * c / (1 + c) if c > -1 else np.nan)
    return pd.DataFrame([{"outcome": k, "reliability": np.nanmedian(v)} for k, v in stats.items()])
