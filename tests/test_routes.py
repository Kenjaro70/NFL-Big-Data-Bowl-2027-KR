"""Known-answer tests for game-route cuts, outcome adjustment and split-half reliability."""
import numpy as np
import pandas as pd

from src import routes as R
from src.cuts import DT
from src.outcomes import MIN_CELL, separation_routes
from src.stats import split_half

CENTER = R.FIELD_CENTER_Y


def test_break_side_inside_and_outside_on_both_sides_and_directions():
    # Offense moving +x; looking downfield, +y is the receiver's left.
    assert R.break_side("R", vx_in=8.0, y_apex=CENTER + 15) == "in"   # left-side WR turns right, toward the middle
    assert R.break_side("L", vx_in=8.0, y_apex=CENTER + 15) == "out"
    assert R.break_side("L", vx_in=8.0, y_apex=CENTER - 15) == "in"   # right-side WR turns left, toward the middle
    # Offense moving -x: same physical rule, mirrored.
    assert R.break_side("R", vx_in=-8.0, y_apex=CENTER - 15) == "in"
    assert R.break_side("L", vx_in=-8.0, y_apex=CENTER - 15) == "out"


def _route(heading_deg, speed, x0, y0, direction):
    """Frames for one route: heading 0 = downfield, positive = toward the receiver's right."""
    h = np.radians(np.asarray(heading_deg, float))
    s = np.asarray(speed, float)
    sgn = 1.0 if direction == "right" else -1.0
    # Looking downfield, the receiver's right is -y when the offense moves +x, and +y when it moves -x.
    vx, vy = sgn * s * np.cos(h), -sgn * s * np.sin(h)
    x, y = x0 + np.cumsum(vx) * DT, y0 + np.cumsum(vy) * DT
    t = pd.Timestamp("2024-09-08 13:00:00") + pd.to_timedelta(np.arange(len(s)) * DT, unit="s")
    return pd.DataFrame({"time": t, "x": x, "y": y, "s": s})


def test_slant_from_left_side_is_an_inside_break_at_route_depth():
    # Left-side WR (looking downfield): accelerate 1.5 s, slant 50 degrees inside (toward the receiver's right).
    speed = np.r_[np.linspace(0, 7, 15), np.full(25, 7.0)]
    heading = np.r_[np.zeros(17), np.linspace(0, 50, 5), np.full(18, 50.0)]
    for direction, x0, y0 in [("right", 30.0, CENTER + 12), ("left", 90.0, CENTER - 12)]:
        f = _route(heading, speed, x0, y0, direction).assign(game_id=1, play_id=1, nfl_id=7)
        routes = pd.DataFrame({"game_id": [1], "play_id": [1], "nfl_id": [7], "route_ran": ["SLANT"],
                               "play_direction": [direction], "ttt": [2.5]})
        (cut,) = R.route_cuts(f, routes).to_dict("records")
        assert cut["break_side"] == "in", direction
        assert 6 <= cut["depth"] <= 15, direction
        assert cut["kept"]



def test_break_before_its_entry_window_clears_the_snap_is_not_kept():
    # Quick release: up to speed in 0.5 s, then a 60-degree inside turn about 3 yd downfield at ~0.9 s.
    speed = np.r_[np.linspace(0, 6, 6), np.full(24, 6.0)]
    heading = np.r_[np.zeros(8), np.linspace(0, 60, 3), np.full(19, 60.0)]
    f = _route(heading, speed, 30.0, CENTER + 12, "right").assign(game_id=1, play_id=1, nfl_id=7)
    routes = pd.DataFrame({"game_id": [1], "play_id": [1], "nfl_id": [7], "route_ran": ["SLANT"],
                           "play_direction": ["right"], "ttt": [2.0]})
    (cut,) = R.route_cuts(f, routes).to_dict("records")
    assert cut["t_after_snap"] < R.MIN_APEX_AFTER_SNAP
    assert cut["depth"] >= R.MIN_DEPTH  # deep enough to be a break; dropped only for timing
    assert not cut["kept"]

def test_slot_adjustment_removes_depth_and_angle():
    rng = np.random.default_rng(0)
    n = 400
    c = pd.DataFrame({"route_ran": "OUT", "break_side": "out", "depth": rng.uniform(3, 15, n),
                      "turn_deg": rng.uniform(40, 110, n)})
    for m in R.METRICS:
        c[m] = 0.5 * c.depth - 0.02 * c.turn_deg + rng.normal(0, 1, n)
    z = R.slot_z_adjusted(c)
    for m in R.METRICS:
        assert abs(z[f"{m}_z"].corr(z.depth)) < 0.05
        assert abs(z[f"{m}_z"].corr(z.turn_deg)) < 0.05
        assert abs(z[f"{m}_z"].std() - 1) < 0.01


def test_split_half_separates_stable_traits_from_noise():
    rng = np.random.default_rng(1)
    players, games, per_game = 60, 12, 10
    pid = np.repeat(np.arange(players), games * per_game)
    gid = np.tile(np.repeat(np.arange(games), per_game), players)
    trait = rng.normal(0, 1, players)[pid]
    obs = pd.DataFrame({"nfl_id": pid, "game_id": gid,
                        "stable": trait + rng.normal(0, 1, len(pid)),
                        "noise": rng.normal(0, 1, len(pid))})
    rel = split_half(obs, ["stable", "noise"], n_iter=50).set_index("feature").reliability
    assert rel["stable"] > 0.9
    assert abs(rel["noise"]) < 0.3


def test_expected_separation_falls_back_to_coarser_cells():
    big = MIN_CELL + 10
    r = pd.DataFrame({
        "route_ran": ["OUT"] * (big + 5),
        "coverage": ["ZONE_COVERAGE"] * (big + 5),
        "ttt": [2.2] * big + [4.0] * 5,             # the >=3.5 s cell has only 5 routes
        "separation": [3.0] * big + [6.0] * 5,
    })
    s = separation_routes(r)
    assert np.allclose(s.expected_separation.iloc[:big], 3.0)
    pooled = (3.0 * big + 6.0 * 5) / (big + 5)  # falls back to the route x coverage mean
    assert np.allclose(s.expected_separation.iloc[big:], pooled)
