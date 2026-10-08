"""Synthetic trajectories with known answers for the cut detector."""
import numpy as np

from src.cuts import DT, detect_cuts, kinematics


def path_from(speed, heading_deg):
    """Integrate per-frame speed (yd/s) and heading (deg, clockwise from +y) into x, y."""
    h = np.radians(heading_deg)
    vx, vy = speed * np.sin(h), speed * np.cos(h)
    return np.cumsum(vx) * DT, np.cumsum(vy) * DT


def cuts_of(speed, heading):
    return detect_cuts(kinematics(*path_from(np.asarray(speed, float), np.asarray(heading, float))))


def test_straight_line_has_no_cuts():
    speed = np.r_[np.linspace(0, 8, 20), np.full(40, 8.0)]
    assert cuts_of(speed, np.zeros(60)) == []


def test_rounded_90_degree_right_turn():
    speed = np.r_[np.linspace(0, 7, 20), np.full(50, 7.0)]
    heading = np.r_[np.zeros(30), np.linspace(0, 90, 10), np.full(30, 90.0)]  # turn toward +x
    (cut,) = cuts_of(speed, heading)
    assert cut["turn_dir"] == "R"
    assert 60 <= cut["turn_deg"] <= 95
    assert 30 <= cut["apex_frame"] <= 40
    assert cut["peak_lat_accel"] > 3


def test_plant_and_reverse_left():
    # Sprint, brake to a near stop while turning left, sprint back the other way.
    speed = np.r_[np.linspace(0, 6, 15), np.full(10, 6.0), np.linspace(6, 0.3, 8), np.linspace(0.3, 6, 12), np.full(10, 6.0)]
    heading = np.r_[np.zeros(29), np.linspace(0, -180, 8), np.full(18, -180.0)]  # counter-clockwise
    (cut,) = cuts_of(speed, heading)
    assert cut["turn_dir"] == "L"
    assert cut["turn_deg"] > 150
    assert cut["apex_speed"] < 1.5
    assert cut["speed_retention"] < 0.25
    assert cut["peak_decel"] > 5
    assert cut["reaccel_gain"] > 2


def test_two_breaks_in_opposite_directions():
    speed = np.r_[np.linspace(0, 7, 15), np.full(65, 7.0)]
    heading = np.r_[np.zeros(25), np.linspace(0, -60, 6), np.full(20, -60.0), np.linspace(-60, 30, 6), np.full(23, 30.0)]
    cuts = cuts_of(speed, heading)
    assert [c["turn_dir"] for c in cuts] == ["L", "R"]
