"""Cut detection and per-cut mechanics from 10 Hz x/y tracking.

Works on any single-player trajectory (a combine rep or an in-game route), and
derives everything from smoothed x/y so combine and game data get identical
processing. The provided `a` is an unsigned magnitude in both sources, so it is
not used.

A cut is a local peak in the signed turn angle between the velocity vectors
HALF_WINDOW before and after a frame. Using velocities on either side, rather
than frame-to-frame heading, keeps plant-and-reverse breaks measurable: the
heading is undefined at the near-zero apex speed of a shuttle turn or a curl.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.signal import find_peaks, savgol_filter

HZ = 10
DT = 1 / HZ

# Smoothing: Savitzky-Golay over 0.7 s, quadratic.
SG_WINDOW = 7
SG_POLY = 2

# Detection.
HALF_WINDOW = 5      # frames (0.5 s) either side for the turn angle
MIN_TURN = 30.0      # degrees
MIN_SEP = 5          # frames between peaks of the same direction
APEX_SEARCH = 3      # frames either side of the turn peak to find the speed minimum
MERGE_WITHIN = 4     # frames: apexes closer than this are one cut
MIN_MOVING = 1.0     # yd/s: both velocity vectors must be at least this fast
MIN_ENTRY = 2.0      # yd/s: peak speed into the cut
MIN_EXIT = 1.5       # yd/s: peak speed out of the cut

# Metric windows (frames).
ENTRY_WINDOW = 15    # 1.5 s before the apex
DECEL_WINDOW = 10    # 1.0 s before the apex
EXIT_WINDOW = 10     # 1.0 s after the apex
LOAD_WINDOW = 5      # 0.5 s either side of the apex
GAIN_FRAMES = 5      # speed gained 0.5 s after the apex


def kinematics(x: np.ndarray, y: np.ndarray) -> dict[str, np.ndarray]:
    """Smoothed velocity and acceleration, split into along-track and lateral parts.

    Signs: `a_long` > 0 speeding up, < 0 slowing down. `a_lat` and `turn_rate`
    > 0 turning left (counter-clockwise viewed from above), < 0 turning right.
    """
    n = len(x)
    w = min(SG_WINDOW, n if n % 2 else n - 1)
    if w <= SG_POLY:
        raise ValueError(f"trajectory too short ({n} frames)")
    vx = savgol_filter(x, w, SG_POLY, deriv=1, delta=DT)
    vy = savgol_filter(y, w, SG_POLY, deriv=1, delta=DT)
    ax = savgol_filter(x, w, SG_POLY, deriv=2, delta=DT)
    ay = savgol_filter(y, w, SG_POLY, deriv=2, delta=DT)
    speed = np.hypot(vx, vy)
    safe = np.where(speed > 1e-6, speed, np.nan)
    a_long = (vx * ax + vy * ay) / safe
    a_lat = (vx * ay - vy * ax) / safe
    return {
        "vx": vx, "vy": vy, "speed": speed,
        "a_long": np.nan_to_num(a_long),
        "a_lat": np.nan_to_num(a_lat),
        "turn_rate": np.where(speed > MIN_MOVING, a_lat / safe, 0.0),  # rad/s
    }


def turn_angle(vx: np.ndarray, vy: np.ndarray, half: int = HALF_WINDOW) -> np.ndarray:
    """Signed angle (deg) from the velocity `half` frames before to `half` frames after.

    > 0 is a left turn. 0 where either vector is slower than MIN_MOVING or out of range.
    """
    n = len(vx)
    theta = np.zeros(n)
    if n <= 2 * half:
        return theta
    i = np.arange(half, n - half)
    x1, y1, x2, y2 = vx[i - half], vy[i - half], vx[i + half], vy[i + half]
    ang = np.degrees(np.arctan2(x1 * y2 - y1 * x2, x1 * x2 + y1 * y2))
    moving = (np.hypot(x1, y1) >= MIN_MOVING) & (np.hypot(x2, y2) >= MIN_MOVING)
    theta[i] = np.where(moving, ang, 0.0)
    return theta


def detect_cuts(k: dict[str, np.ndarray]) -> list[dict]:
    """Cuts in one trajectory, as dicts of apex index, signed turn and metrics."""
    speed, a_long, a_lat = k["speed"], k["a_long"], k["a_lat"]
    n = len(speed)
    theta = turn_angle(k["vx"], k["vy"])

    cands = []
    for sign in (1, -1):
        peaks, _ = find_peaks(sign * theta, height=MIN_TURN, distance=MIN_SEP)
        for p in peaks:
            lo, hi = max(p - APEX_SEARCH, 0), min(p + APEX_SEARCH + 1, n)
            apex = lo + int(np.argmin(speed[lo:hi]))
            cands.append((apex, float(theta[p])))

    # Merge candidates whose apexes coincide (keep the larger turn).
    cands.sort(key=lambda c: -abs(c[1]))
    kept: list[tuple[int, float]] = []
    for apex, th in cands:
        if all(abs(apex - a) >= MERGE_WITHIN for a, _ in kept):
            kept.append((apex, th))
    kept.sort()

    cuts = []
    for apex, th in kept:
        e0 = max(apex - ENTRY_WINDOW, 0)
        entry_i = e0 + int(np.argmax(speed[e0:apex + 1]))
        entry_speed = float(speed[entry_i])
        x1 = min(apex + EXIT_WINDOW + 1, n)
        exit_speed = float(speed[apex:x1].max())
        if entry_speed < MIN_ENTRY or exit_speed < MIN_EXIT:
            continue
        apex_speed = float(speed[apex])
        d0 = max(apex - DECEL_WINDOW, 0)
        l0, l1 = max(apex - LOAD_WINDOW, 0), min(apex + LOAD_WINDOW + 1, n)
        gain_i = apex + GAIN_FRAMES
        # Distance travelled while slowing from entry speed to the apex.
        decel_dist = float(np.sum(speed[entry_i:apex]) * DT)
        cuts.append({
            "apex_frame": apex,
            "turn_deg": abs(th),
            "turn_dir": "L" if th > 0 else "R",
            "entry_speed": entry_speed,
            "apex_speed": apex_speed,
            "exit_speed": exit_speed,
            "speed_retention": apex_speed / entry_speed,
            "peak_decel": float(-a_long[d0:apex + 1].min()),
            "decel_time": (apex - entry_i) * DT,
            "decel_dist": decel_dist,
            "peak_lat_accel": float(np.abs(a_lat[l0:l1]).max()),
            "reaccel_gain": float(speed[gain_i] - apex_speed) if gain_i < n else np.nan,
            "peak_reaccel": float(a_long[apex:x1].max()) if x1 - apex >= 3 else np.nan,
            "frames_after_apex": n - 1 - apex,
        })
    return cuts


def cuts_for_reps(frames: pd.DataFrame, rep_cols: list[str]) -> pd.DataFrame:
    """Detect cuts in every rep. `frames` needs rep_cols + time, x, y."""
    out = []
    for key, r in frames.sort_values([*rep_cols, "time"]).groupby(rep_cols, sort=False):
        if len(r) <= 2 * HALF_WINDOW:
            continue
        k = kinematics(r["x"].to_numpy(float), r["y"].to_numpy(float))
        key = key if isinstance(key, tuple) else (key,)
        for i, c in enumerate(detect_cuts(k)):
            out.append({**dict(zip(rep_cols, key)), "cut_idx": i, "n_frames": len(r), **c})
    return pd.DataFrame(out)
