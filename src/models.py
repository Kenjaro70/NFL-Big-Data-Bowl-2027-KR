"""Regression helpers for Phase 3: OLS with robust or player-clustered errors, ridge, bootstrap, Holm.

numpy / scipy only. Every model adds its own intercept; pass predictors without one.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

UDFA_PICK = 260  # UDFAs sit just after the last pick (256 in this cohort); a UDFA indicator goes alongside


def baseline_matrix(df: pd.DataFrame, medians: pd.Series | None = None) -> tuple[pd.DataFrame, pd.Series]:
    """The pre-registered baseline: log(draft pick) with UDFAs at pick 260, a UDFA flag, 40, 10-yd split,
    vertical, broad jump, height, weight. Missing tests are filled with `medians` (default: this sample's)."""
    b = pd.DataFrame({
        "log_pick": np.log(df.draft_overall_pick.fillna(UDFA_PICK).astype(float)),
        "udfa": df.draft_overall_pick.isna().astype(float),
        "forty": df.forty, "ten_yd_split": df.ten_yd_split, "vertical": df.vertical,
        "broad_jump": df.broad_jump, "height": df.combine_height, "weight": df.combine_weight,
    }, index=df.index).astype(float)
    medians = b.median() if medians is None else medians
    return b.fillna(medians), medians


def zscore(X: pd.DataFrame, ref: pd.DataFrame | None = None) -> pd.DataFrame:
    """Standardize with `ref`'s mean and SD (default: X's own). Constant columns become 0."""
    ref = X if ref is None else ref
    sd = ref.std(ddof=0).replace(0, 1.0)
    return (X - ref.mean()) / sd


def ols(y: np.ndarray, X: np.ndarray, cluster: np.ndarray | None = None) -> dict:
    """OLS of y on [1, X]. Standard errors are HC3, or CR1 when `cluster` labels are given.

    p-values use a t distribution with n - k degrees of freedom (HC3) or G - 1 (CR1, G clusters).
    `partial_r` is the partial correlation of each predictor with y, from the classical t:
    t / sqrt(t^2 + n - k).
    """
    y = np.asarray(y, float)
    X1 = np.column_stack([np.ones(len(y)), np.asarray(X, float)])
    n, k = X1.shape
    XtX_inv = np.linalg.pinv(X1.T @ X1)
    beta = XtX_inv @ X1.T @ y
    e = y - X1 @ beta
    if cluster is None:
        h = np.einsum("ij,jk,ik->i", X1, XtX_inv, X1)
        meat = (X1 * (e / (1 - h))[:, None] ** 2).T @ X1
        df = n - k
    else:
        codes, groups = pd.factorize(np.asarray(cluster))
        G = len(groups)
        scores = np.zeros((G, k))
        np.add.at(scores, codes, X1 * e[:, None])
        meat = scores.T @ scores * (G / (G - 1)) * ((n - 1) / (n - k))
        df = G - 1
    se = np.sqrt(np.diag(XtX_inv @ meat @ XtX_inv))
    t = beta / se
    t_classical = beta / np.sqrt(np.diag(XtX_inv) * (e @ e) / (n - k))
    return {
        "coef": beta, "se": se, "t": t, "p": 2 * stats.t.sf(np.abs(t), df),
        "partial_r": t_classical / np.sqrt(t_classical ** 2 + (n - k)), "n": n, "df": df,
    }


def ridge_gcv(X: np.ndarray, y: np.ndarray, lambdas: np.ndarray | None = None) -> tuple[float, np.ndarray, float]:
    """Ridge on standardized-by-caller X with the penalty chosen by generalized cross-validation.

    Returns (intercept, coefficients, lambda). The intercept is not penalized.
    """
    X, y = np.asarray(X, float), np.asarray(y, float)
    lambdas = np.logspace(-3, 3, 61) * len(y) if lambdas is None else lambdas
    xm, ym = X.mean(axis=0), y.mean()
    Xc, yc = X - xm, y - ym
    U, d, Vt = np.linalg.svd(Xc, full_matrices=False)
    uty = U.T @ yc
    best = None
    for lam in lambdas:
        f = d ** 2 / (d ** 2 + lam)
        fit = U @ (f * uty)
        gcv = len(y) * np.sum((yc - fit) ** 2) / (len(y) - f.sum()) ** 2
        if best is None or gcv < best[0]:
            best = (gcv, lam)
    lam = best[1]
    beta = Vt.T @ ((d / (d ** 2 + lam)) * uty)
    return ym - xm @ beta, beta, lam


def leave_one_group_out(df: pd.DataFrame, target: str, build, group: str) -> pd.Series:
    """Out-of-sample ridge predictions of `target`, holding out one value of `group` at a time.

    `build(train, test)` returns (X_train, X_test) as DataFrames; it sees only the training rows when it
    computes anything from data (medians, means, SDs), so nothing from the held-out group leaks in.
    """
    pred = pd.Series(np.nan, index=df.index)
    for g in df[group].unique():
        train, test = df[df[group] != g], df[df[group] == g]
        Xtr, Xte = build(train, test)
        a, b, _ = ridge_gcv(Xtr.to_numpy(), train[target].to_numpy())
        pred[test.index] = a + Xte.to_numpy() @ b
    return pred


def oos_r2(y: pd.Series, pred: pd.Series) -> float:
    """Pooled out-of-sample R^2: 1 - SSE / total sum of squares around the pooled mean."""
    return float(1 - np.sum((y - pred) ** 2) / np.sum((y - y.mean()) ** 2))


def bootstrap(stat, units: np.ndarray, n_boot: int = 2000, seed: int = 0) -> np.ndarray:
    """`stat(index)` over `n_boot` resamples of `units` (players) with replacement.

    `index` is an integer array of positions into `units`; with clusters, the caller expands each drawn
    unit to its rows. Failed resamples (e.g. a singular fit) come back as NaN.
    """
    rng = np.random.default_rng(seed)
    out = np.full(n_boot, np.nan)
    for i in range(n_boot):
        try:
            out[i] = stat(rng.integers(0, len(units), len(units)))
        except (np.linalg.LinAlgError, ValueError, ZeroDivisionError):
            pass
    return out


def percentile_ci(draws: np.ndarray, level: float = 0.95) -> tuple[float, float]:
    a = (1 - level) / 2
    lo, hi = np.nanquantile(draws, [a, 1 - a])
    return float(lo), float(hi)


def holm(p) -> np.ndarray:
    """Holm-adjusted p-values, in the input order."""
    p = np.asarray(p, float)
    order = np.argsort(p)
    m = len(p)
    adj = np.maximum.accumulate((m - np.arange(m)) * p[order])
    out = np.empty(m)
    out[order] = np.minimum(adj, 1.0)
    return out
