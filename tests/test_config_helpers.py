import tempfile
from pathlib import Path

from config_helpers import DEFAULT_CONFIG, load_json_config, save_json_config


def test_load_missing_returns_default():
    with tempfile.TemporaryDirectory() as tmp:
        data = load_json_config(Path(tmp) / "missing.json")
    assert data == DEFAULT_CONFIG


def test_save_and_load_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.json"
        data = {"accounts": [{"openid": "abc"}], "open_time": "x", "pref": "1"}
        assert save_json_config(path, data)
        assert load_json_config(path)["accounts"][0]["openid"] == "abc"


def test_corrupted_config_is_backed_up():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.json"
        path.write_text("{broken", encoding="utf-8")
        data = load_json_config(path)
        assert data == DEFAULT_CONFIG
        assert path.with_suffix(".json.corrupted.bak").exists()


if __name__ == "__main__":
    test_load_missing_returns_default()
    test_save_and_load_roundtrip()
    test_corrupted_config_is_backed_up()
    print("test_config_helpers ok")
