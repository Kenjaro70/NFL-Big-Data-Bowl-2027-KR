"""Slot scoring: the turn-angle adjustment separates a player's mechanics from how sharp their breaks were."""
import numpy as np
import pandas as pd

from src.features import player_features, slot_z


def test_slot_z_adjusts_for_turn_angle():
    rng = np.random.default_rng(0)
    rows = []
    for player, (skill, sharpness) in enumerate([(+0.1, 30), (0.0, 60), (-0.1, 90)]):
        for rep in range(40):
            turn = sharpness + rng.normal(0, 5)
            # Retention falls with sharper breaks; within that, player 0 keeps the most speed.
            rows.append({"event_id": f"{player}_{rep}", "nfl_id": player, "drill_name": "D", "turn_dir": "L",
                         "apex_frame": 10, "turn_deg": turn,
                         "speed_retention": 1.0 - turn / 120 + skill + rng.normal(0, 0.02)})
    cuts = pd.DataFrame(rows)
    raw = player_features(slot_z(cuts, True, metrics=("speed_retention",), covariates=()), "f",
                          metrics=("speed_retention",))
    adj = player_features(slot_z(cuts, True, metrics=("speed_retention",)), "f", metrics=("speed_retention",))
    # Unadjusted, the gentle-breaking player looks best by a wide margin; adjusted, the skill order holds
    # and the gap shrinks to what skill alone explains.
    assert raw["f_speed_retention"].idxmax() == 0
    assert adj["f_speed_retention"].is_monotonic_decreasing
    spread = lambda f: f["f_speed_retention"].max() - f["f_speed_retention"].min()
    assert spread(adj) < spread(raw)


def test_slot_z_drops_small_slots():
    cuts = pd.DataFrame({"event_id": [f"r{i}" for i in range(5)], "nfl_id": 1, "drill_name": "D",
                         "turn_dir": "L", "apex_frame": 10, "turn_deg": 45.0, "speed_retention": 0.9})
    assert slot_z(cuts, True, metrics=("speed_retention",)).empty
