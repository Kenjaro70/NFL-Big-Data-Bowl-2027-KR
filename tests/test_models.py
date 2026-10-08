"""Known-answer tests for the Phase 3 model helpers."""
import numpy as np
import pandas as pd

from src import models as M


def test_ols_recovers_coefficients_and_hc3_matches_classical_se_when_homoskedastic():
    rng = np.random.default_rng(0)
    n = 4000
    X = rng.normal(size=(n, 2))
    y = 1.0 + 2.0 * X[:, 0] - 0.5 * X[:, 1] + rng.normal(size=n)
    fit = M.ols(y, X)
    assert np.allclose(fit["coef"], [1.0, 2.0, -0.5], atol=0.05)
    classical = np.sqrt(np.diag(np.linalg.inv(np.column_stack([np.ones(n), X]).T @ np.column_stack([np.ones(n), X]))))
    assert np.allclose(fit["se"], classical, rtol=0.1)
    assert fit["p"][1] < 1e-10


def test_partial_r_equals_the_correlation_of_residualized_variables():
    rng = np.random.default_rng(1)
    n = 500
    z = rng.normal(size=n)
    x = 0.6 * z + rng.normal(size=n)
    y = 0.4 * x + 0.8 * z + rng.normal(size=n)
    fit = M.ols(y, np.column_stack([z, x]))
    rx = x - np.polyval(np.polyfit(z, x, 1), z)
    ry = y - np.polyval(np.polyfit(z, y, 1), z)
    assert abs(fit["partial_r"][2] - np.corrcoef(rx, ry)[0, 1]) < 1e-9


def test_clustered_se_grows_with_within_cluster_correlation():
    rng = np.random.default_rng(2)
    G, m = 60, 50
    g = np.repeat(np.arange(G), m)
    x = rng.normal(size=G)[g] + 0.2 * rng.normal(size=G * m)   # predictor varies mostly by cluster
    y = rng.normal(size=G)[g] + rng.normal(size=G * m)         # cluster-level noise, no true effect
    naive = M.ols(y, x[:, None])
    clustered = M.ols(y, x[:, None], cluster=g)
    assert clustered["se"][1] > 3 * naive["se"][1]
    assert clustered["df"] == G - 1


def test_ridge_gcv_approaches_ols_with_strong_signal_and_shrinks_noise():
    rng = np.random.default_rng(3)
    n = 300
    X = rng.normal(size=(n, 3))
    y = 3 * X[:, 0] + 0.1 * rng.normal(size=n)
    a, b, lam = M.ridge_gcv(X, y)
    assert abs(b[0] - 3) < 0.05 and np.all(np.abs(b[1:]) < 0.05)
    a2, b2, lam2 = M.ridge_gcv(X, rng.normal(size=n))
    assert lam2 > lam and np.all(np.abs(b2) < 0.15)


def test_leave_one_group_out_never_uses_the_held_out_group():
    # Each group's target is its own constant; a held-out group can't be predicted from the others
    # unless its rows leak into training.
    df = pd.DataFrame({"g": np.repeat([0, 1, 2], 40), "x": np.tile(np.linspace(-1, 1, 40), 3)})
    df["y"] = df.g.map({0: 0.0, 1: 0.0, 2: 10.0}) + 0.01 * df.x

    def build(train, test):
        return M.zscore(train[["x"]]), M.zscore(test[["x"]], ref=train[["x"]])

    pred = M.leave_one_group_out(df, "y", build, "g")
    assert np.allclose(pred[df.g == 2], 0.0, atol=0.1)   # trained on groups 0 and 1 only
    assert M.oos_r2(df.y, pred) < 0


def test_baseline_fills_missing_tests_and_flags_udfas():
    df = pd.DataFrame({"draft_overall_pick": [10.0, np.nan, 100.0], "forty": [4.4, np.nan, 4.6],
                       "ten_yd_split": 1.5, "vertical": 36.0, "broad_jump": 120.0,
                       "combine_height": 72.0, "combine_weight": 200.0})
    b, med = M.baseline_matrix(df)
    assert b.udfa.tolist() == [0.0, 1.0, 0.0]
    assert np.isclose(b.log_pick.iloc[1], np.log(M.UDFA_PICK))
    assert np.isclose(b.forty.iloc[1], 4.5)
    train_medians = med.copy()
    train_medians["forty"] = 9.9
    b2, _ = M.baseline_matrix(df, medians=train_medians)  # held-out rows use training medians
    assert np.isclose(b2.forty.iloc[1], 9.9)


def test_holm_known_answer():
    assert np.allclose(M.holm([0.01, 0.04, 0.03]), [0.03, 0.06, 0.06])
    assert np.allclose(M.holm([0.5, 0.9]), [1.0, 1.0])


def test_bootstrap_ci_covers_the_mean():
    rng = np.random.default_rng(4)
    x = rng.normal(2.0, 1.0, 200)
    draws = M.bootstrap(lambda idx: x[idx].mean(), x, n_boot=500)
    lo, hi = M.percentile_ci(draws)
    assert lo < 2.0 < hi and hi - lo < 0.4
