"""Small statistics helpers shared across phases."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import norm


def split_half(obs: pd.DataFrame, cols: list[str], unit: str = "game_id", n_iter: int = 200, seed: int = 0,
               min_units: int = 6, players=None) -> pd.DataFrame:
    """Spearman-Brown corrected split-half reliability of per-player means.

    `obs` has one row per observation (a cut, a route) with `nfl_id`, `unit` and `cols`.
    Each iteration splits every player's units (e.g. games) at random into two halves,
    averages each column per player within each half, and correlates the halves
    across players. Only `players` are used, if given; players with fewer than
    `min_units` units are left out.

    Restrict to players with enough volume: a few low-volume players have such
    noisy half-means that they drag the correlation down for everyone.
    """
    rng = np.random.default_rng(seed)
    d = obs if players is None else obs[obs.nfl_id.isin(players)]
    d = d[d.groupby("nfl_id")[unit].transform("nunique") >= min_units]
    units = d[["nfl_id", unit]].drop_duplicates()
    stats: dict[str, list[float]] = {c: [] for c in cols}
    for _ in range(n_iter):
        half = units.assign(h=rng.random(len(units)))
        half["h"] = half.groupby("nfl_id")["h"].rank(method="first") % 2
        dd = d.merge(half, on=["nfl_id", unit])
        a = dd[dd.h == 0].groupby("nfl_id")[cols].mean()
        b = dd[dd.h == 1].groupby("nfl_id")[cols].mean()
        for c in cols:
            r = a[c].corr(b[c])
            stats[c].append(2 * r / (1 + r) if r > -1 else np.nan)
    players = d["nfl_id"].nunique()
    return pd.DataFrame([{"feature": c, "reliability": np.nanmedian(v), "players": players} for c, v in stats.items()])


def detectable_r(n: int, alpha: float = 0.05, power: float = 0.8) -> float:
    """Smallest |Pearson r| a two-sided test detects with the given power at sample size n (Fisher z)."""
    return float(np.tanh((norm.ppf(1 - alpha / 2) + norm.ppf(power)) / np.sqrt(n - 3)))
