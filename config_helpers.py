import json
import os
import shutil
from pathlib import Path
from typing import Any


DEFAULT_CONFIG: dict[str, Any] = {
    "accounts": [],
    "open_time": "",
    "pref": "1",
    "mask_sensitive": True,
}


def load_json_config(path: str | os.PathLike[str], default: dict[str, Any] | None = None) -> dict[str, Any]:
    config_path = Path(path)
    fallback = dict(default or DEFAULT_CONFIG)
    if not config_path.exists():
        return fallback
    try:
        with config_path.open("r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except Exception:
        backup = config_path.with_suffix(config_path.suffix + ".corrupted.bak")
        try:
            shutil.copy2(config_path, backup)
        except Exception:
            pass
        return fallback
    if not isinstance(data, dict):
        return fallback
    merged = dict(fallback)
    merged.update(data)
    if not isinstance(merged.get("accounts"), list):
        merged["accounts"] = []
    return merged


def save_json_config(path: str | os.PathLike[str], data: dict[str, Any]) -> bool:
    config_path = Path(path)
    tmp_path = config_path.with_suffix(config_path.suffix + ".tmp")
    backup_path = config_path.with_suffix(config_path.suffix + ".bak")
    try:
        if config_path.exists():
            shutil.copy2(config_path, backup_path)
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, config_path)
        return True
    except Exception:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception:
            pass
        return False
