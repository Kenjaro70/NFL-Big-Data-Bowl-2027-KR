"""The raw-data location can be moved (e.g. to Kaggle's read-only input folder)."""
import importlib

from src import data


def test_raw_dir_defaults_to_data_raw_and_follows_bdb_raw_dir(monkeypatch, tmp_path):
    monkeypatch.delenv("BDB_RAW_DIR", raising=False)
    assert importlib.reload(data).RAW == data.ROOT / "data" / "raw"
    monkeypatch.setenv("BDB_RAW_DIR", str(tmp_path))
    assert importlib.reload(data).RAW == tmp_path
    monkeypatch.delenv("BDB_RAW_DIR")
    importlib.reload(data)
