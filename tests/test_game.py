"""Inside/outside: which turn points toward the middle of the field."""
import pandas as pd

from src.game import CENTER_Y, WIDE_MARGIN, inside_direction


def test_inside_direction():
    high, low, middle = CENTER_Y + WIDE_MARGIN + 5, CENTER_Y - WIDE_MARGIN - 5, CENTER_Y + 1
    got = inside_direction(pd.Series(["right", "right", "left", "left", "right"]),
                           pd.Series([high, low, high, low, middle]))
    # Moving toward +x, high y is the offense's left: the middle is a right turn away, and so on.
    assert got.tolist()[:4] == ["R", "L", "L", "R"]
    assert pd.isna(got.iloc[4])  # too close to the center to tell which side of the ball
