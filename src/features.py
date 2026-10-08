"""Player-level combine cut features.

Raw cut metrics are not comparable across breaks (a 180-degree curl costs far
more speed than a 45-degree slant break), and players ran different drill sets.
So each metric is z-scored within its *slot*: the same break of the same drill
across players. A player's feature is the mean of those z-scores over their
cuts, so 0 = average for the breaks they ran.

Slots in route drills are drill x turn direction x order (the curl's plant is
CURL_ROUTE_RIGHT|L1, the turn upfield after the catch is CURL_ROUTE_RIGHT|R1),
because each route breaks a fixed way. In the shuttle and 3-cone the player
chooses which way to turn, so slots there are drill x cut order.
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


def slot_z(cuts: pd.DataFrame, by_direction: bool, metrics=tuple(METRICS)) -> pd.DataFrame:
    """Add `slot` and `<metric>_z` (z-score within slot). Slots with < MIN_CUTS_PER_SLOT cuts are dropped."""
    c = cuts.sort_values(["event_id", "apex_frame"]).copy()
    if by_direction:
        order = c.groupby(["event_id", "turn_dir"]).cumcount() + 1
        c["slot"] = c["drill_name"] + "|" + c["turn_dir"] + order.astype(str)
    else:
        c["slot"] = c["drill_name"] + "|" + (c["cut_idx"] + 1).astype(str)
    c = c[c.groupby("slot")["event_id"].transform("size") >= MIN_CUTS_PER_SLOT].copy()
    for m in metrics:
        g = c.groupby("slot")[m]
        c[f"{m}_z"] = (c[m] - g.transform("mean")) / g.transform("std")
    return c


def player_features(zcuts: pd.DataFrame, prefix: str, metrics=tuple(METRICS)) -> pd.DataFrame:
    """One row per player: mean drill-z per metric, plus left/right asymmetry and consistency.

    `<prefix>_<metric>`          mean z over all cuts
    `<prefix>_<metric>_lr`       mean z on left cuts minus mean z on right cuts
    `<prefix>_<metric>_sd`       SD of z across cuts (lower = more consistent)
    """
    g = zcuts.groupby("nfl_id")
    feats = pd.DataFrame({
        f"{prefix}_n_cuts": g.size(),
        f"{prefix}_n_drills": g["drill_name"].nunique(),
    })
    for m in metrics:
        z = f"{m}_z"
        feats[f"{prefix}_{m}"] = g[z].mean()
        side = zcuts.pivot_table(index="nfl_id", columns="turn_dir", values=z, aggfunc="mean")
        feats[f"{prefix}_{m}_lr"] = side.get("L") - side.get("R")
        feats[f"{prefix}_{m}_sd"] = g[z].std()
    return feats


def split_half_reliability(zcuts: pd.DataFrame, n_iter: int = 200, seed: int = 0,
                           metrics=tuple(METRICS), min_drills: int = 4) -> pd.DataFrame:
    """Spearman-Brown corrected split-half reliability of each player feature.

    Each iteration splits every player's drills at random into two halves (a
    drill's cuts stay together), computes the feature on each half, and
    correlates the halves across players.
    """
    rng = np.random.default_rng(seed)
    z = zcuts[zcuts.groupby("nfl_id")["drill_name"].transform("nunique") >= min_drills]
    pairs = z[["nfl_id", "drill_name"]].drop_duplicates()
    stats = {k: [] for m in metrics for k in (m, f"{m}_lr", f"{m}_sd")}
    for _ in range(n_iter):
        half = pairs.assign(h=rng.random(len(pairs)))
        half["h"] = half.groupby("nfl_id")["h"].rank(method="first") % 2
        zz = z.merge(half, on=["nfl_id", "drill_name"])
        a = player_features(zz[zz.h == 0], "f", metrics)
        b = player_features(zz[zz.h == 1], "f", metrics)
        for k in stats:
            r = a[f"f_{k}"].corr(b[f"f_{k}"])
            stats[k].append(2 * r / (1 + r) if r > -1 else np.nan)
    players = z["nfl_id"].nunique()
    return pd.DataFrame(
        [{"feature": k, "reliability": np.nanmedian(v), "players": players} for k, v in stats.items()]
    )
