"""Player-level cut features (combine drills and game routes).

Raw cut metrics are not comparable across breaks (a 180-degree curl costs far
more speed than a 45-degree slant break), and players ran different drill sets.
So each metric is z-scored within its *slot*: the same break of the same drill
across players, after adjusting for how sharp the break was. A player's feature
is the mean of those z-scores over their cuts, so 0 = average for the breaks
they ran.

Slots in route drills are drill x turn direction x order (the curl's plant is
CURL_ROUTE_RIGHT|L1, the turn upfield after the catch is CURL_ROUTE_RIGHT|R1),
because each route breaks a fixed way. In the shuttle and 3-cone the player
chooses which way to turn, so slots there are drill x cut order.

Game routes use the same scheme with the route type in place of the drill
(`base="route_ran"`), extra adjustments for play design (`covariates`, see
`src/game.py`), and games in place of drills as the unit for split-half
reliability (`unit="game_id"`).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.cuts import cuts_for_reps

# metric -> description
METRICS = {
    "entry_speed": "speed into the break (yd/s)",
    "speed_retention": "apex speed / entry speed",
    "peak_decel": "peak braking (yd/s^2)",
    "decel_dist": "distance used to slow down (yd)",
    "peak_lat_accel": "peak lateral (turning) acceleration (yd/s^2)",
    "reaccel_gain": "speed regained 0.5 s after the apex (yd/s)",
}
POSITION_DRILLS = ("SKILL_DRILLS_WR",)
AGILITY_DRILLS = ("SHORT_SHUTTLE", "THREE_CONE_DRILL")
MIN_CUTS_PER_SLOT = 20


def combine_cuts(con, drill_types: tuple[str, ...]) -> pd.DataFrame:
    """Detect cuts in every combine rep of the given drill types."""
    types = ", ".join(f"'{t}'" for t in drill_types)
    frames = con.sql(
        f"""SELECT event_id, nfl_id, drill_type, drill_name, time, x, y
            FROM combine_tracking WHERE entity_type = 'PLAYER' AND drill_type IN ({types})"""
    ).df()
    cuts = cuts_for_reps(frames, ["event_id"])
    reps = frames.drop_duplicates("event_id").set_index("event_id")[["nfl_id", "drill_type", "drill_name"]]
    return cuts.join(reps, on="event_id")


def slot_z(cuts: pd.DataFrame, by_direction: bool, metrics=tuple(METRICS), base: str = "drill_name",
           rep: str = "event_id", covariates: tuple[str, ...] = ("turn_deg",)) -> pd.DataFrame:
    """Add `slot` and `<metric>_z`: the metric's residual within its slot after a linear fit on
    `covariates`, divided by the slot's residual SD. Slots with < MIN_CUTS_PER_SLOT cuts are dropped.

    The default adjusts for the turn angle, so breaks are compared at equal sharpness: a sharper
    break has to cost more speed. `base` names the drill (or route type) column and `rep` the
    column identifying one rep (or route).
    """
    c = cuts.sort_values([rep, "apex_frame"]).copy()
    if by_direction:
        order = c.groupby([rep, "turn_dir"]).cumcount() + 1
        c["slot"] = c[base] + "|" + c["turn_dir"] + order.astype(str)
    else:
        order = c.groupby(rep).cumcount() + 1
        c["slot"] = c[base] + "|" + order.astype(str)
    c = c[c.groupby("slot")[rep].transform("size") >= MIN_CUTS_PER_SLOT].copy()
    for m in metrics:
        c[f"{m}_z"] = np.nan
    for _, idx in c.groupby("slot").groups.items():
        d = c.loc[idx]
        cov = d[list(covariates)].to_numpy(float).reshape(len(d), len(covariates))
        cov = cov[:, np.nan_to_num(np.nanstd(cov, axis=0)) > 0]  # drop covariates constant within the slot
        X = np.column_stack([np.ones(len(d)), cov])
        for m in metrics:
            y = d[m].to_numpy(float)
            ok = np.isfinite(y) & np.isfinite(X).all(axis=1)
            if ok.sum() < MIN_CUTS_PER_SLOT:
                continue
            beta, *_ = np.linalg.lstsq(X[ok], y[ok], rcond=None)
            r = y - X @ beta
            c.loc[idx, f"{m}_z"] = np.where(ok, r / np.std(r[ok], ddof=X.shape[1]), np.nan)
    return c


def player_features(zcuts: pd.DataFrame, prefix: str, metrics=tuple(METRICS),
                    unit: str = "drill_name", unit_label: str = "drills") -> pd.DataFrame:
    """One row per player: mean slot-z per metric, plus left/right asymmetry and consistency.

    `<prefix>_n_cuts`, `<prefix>_n_<unit_label>`  cuts and distinct units (drills or games) behind the row

    `<prefix>_<metric>`          mean z over all cuts
    `<prefix>_<metric>_lr`       mean z on left cuts minus mean z on right cuts
    `<prefix>_<metric>_sd`       SD of z across cuts (lower = more consistent)
    """
    g = zcuts.groupby("nfl_id")
    feats = pd.DataFrame({
        f"{prefix}_n_cuts": g.size(),
        f"{prefix}_n_{unit_label}": g[unit].nunique(),
    })
    for m in metrics:
        z = f"{m}_z"
        feats[f"{prefix}_{m}"] = g[z].mean()
        side = zcuts.pivot_table(index="nfl_id", columns="turn_dir", values=z, aggfunc="mean")
        side = side.reindex(columns=["L", "R"])  # a subset may hold no cuts in one direction
        feats[f"{prefix}_{m}_lr"] = side["L"] - side["R"]
        feats[f"{prefix}_{m}_sd"] = g[z].std()
    return feats


def split_half_reliability(zcuts: pd.DataFrame, n_iter: int = 200, seed: int = 0,
                           metrics=tuple(METRICS), min_units: int = 4, unit: str = "drill_name") -> pd.DataFrame:
    """Spearman-Brown corrected split-half reliability of each player feature.

    Each iteration splits every player's units (drills, or games) at random into
    two halves (a unit's cuts stay together), computes the feature on each half,
    and correlates the halves across players with at least `min_units` units.
    """
    rng = np.random.default_rng(seed)
    z = zcuts[zcuts.groupby("nfl_id")[unit].transform("nunique") >= min_units]
    pairs = z[["nfl_id", unit]].drop_duplicates().sort_values(["nfl_id", unit])
    stats = {k: [] for m in metrics for k in (m, f"{m}_lr", f"{m}_sd")}
    for _ in range(n_iter):
        half = pairs.assign(h=rng.random(len(pairs)))
        half["h"] = half.groupby("nfl_id")["h"].rank(method="first") % 2
        zz = z.merge(half, on=["nfl_id", unit])
        a = player_features(zz[zz.h == 0], "f", metrics, unit=unit)
        b = player_features(zz[zz.h == 1], "f", metrics, unit=unit)
        for k in stats:
            r = a[f"f_{k}"].corr(b[f"f_{k}"])
            stats[k].append(2 * r / (1 + r) if r > -1 else np.nan)
    players = z["nfl_id"].nunique()
    return pd.DataFrame(
        [{"feature": k, "reliability": np.nanmedian(v), "players": players} for k, v in stats.items()]
    )
