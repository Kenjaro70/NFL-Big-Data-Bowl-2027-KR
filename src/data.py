"""Data access: CSV -> Parquet conversion and a DuckDB connection with the
standard views every phase uses.

Named `data` rather than `io` so it never shadows the stdlib module.
"""
from __future__ import annotations

from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PARQUET = ROOT / "data" / "parquet"

TABLES = [
    "players",
    "combine_results",
    "combine_tracking",
    "games",
    "player_play",
    "player_career_successes",
]
GAME_TRACKING_SEASONS = [2023, 2024, 2025]


def to_parquet(overwrite: bool = False) -> None:
    """Convert every CSV in data/raw/ to data/parquet/ (NA -> NULL)."""
    PARQUET.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    for csv in sorted(RAW.glob("*.csv")):
        out = PARQUET / f"{csv.stem}.parquet"
        if out.exists():
            if not overwrite:
                continue
            out.unlink()
        # sample_size=-1: infer types from the whole file (many columns are
        # NA for thousands of rows before the first real value).
        con.execute(
            f"COPY (SELECT * FROM read_csv('{csv}', nullstr='NA', sample_size=-1)) "
            f"TO '{out}' (FORMAT parquet)"
        )


def connect() -> duckdb.DuckDBPyConnection:
    """In-memory DuckDB connection with one view per table, plus:

    game_tracking      all tracking frames, tagged with season / season_type / week
    game_tracking_reg  regular-season frames only (the competition's outcome window)
    player_play_reg    regular-season player-play rows only
    """
    if not (PARQUET / "players.parquet").exists():
        to_parquet()
    con = duckdb.connect()
    for t in TABLES:
        con.execute(f"CREATE VIEW {t} AS SELECT * FROM '{PARQUET / t}.parquet'")
    files = ", ".join(f"'{PARQUET}/game_tracking_{y}.parquet'" for y in GAME_TRACKING_SEASONS)
    con.execute(
        f"""CREATE VIEW game_tracking AS
        SELECT t.*, g.season, g.season_type, g.week
        FROM read_parquet([{files}]) t JOIN games g USING (game_id)"""
    )
    con.execute("CREATE VIEW game_tracking_reg AS SELECT * FROM game_tracking WHERE season_type = 'REG'")
    con.execute(
        """CREATE VIEW player_play_reg AS
        SELECT pp.*, g.season, g.week
        FROM player_play pp JOIN games g USING (game_id)
        WHERE g.season_type = 'REG'"""
    )
    return con
