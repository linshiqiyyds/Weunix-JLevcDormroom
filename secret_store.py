from __future__ import annotations

import base64
import json
import os
from pathlib import Path


class SecretStore:
    """Small local key-value store for non-critical desktop secrets.

    This is obfuscation, not cryptographic protection. It avoids plain-text
    casual exposure without adding platform-specific dependencies.
    """

    def __init__(self, path: str | os.PathLike[str] = "secrets.json"):
        self.path = Path(path)
        self._data: dict[str, str] = {}
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            self._data = {}
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            self._data = {}
            return
        self._data = raw if isinstance(raw, dict) else {}

    def save(self) -> None:
        self.path.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")

    def set(self, key: str, value: str) -> None:
        self._data[key] = encode_secret(value)
        self.save()

    def get(self, key: str, default: str = "") -> str:
        value = self._data.get(key)
        if not value:
            return default
        try:
            return decode_secret(value)
        except Exception:
            return default

    def delete(self, key: str) -> None:
        self._data.pop(key, None)
        self.save()


def encode_secret(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii")


def decode_secret(value: str) -> str:
    return base64.urlsafe_b64decode(value.encode("ascii")).decode("utf-8")
