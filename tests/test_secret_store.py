import tempfile
from pathlib import Path

from secret_store import SecretStore, decode_secret, encode_secret


def test_encode_decode_secret():
    assert decode_secret(encode_secret("hello")) == "hello"


def test_secret_store_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "secrets.json"
        store = SecretStore(path)
        store.set("token", "abc")
        assert SecretStore(path).get("token") == "abc"
        store.delete("token")
        assert SecretStore(path).get("token") == ""


if __name__ == "__main__":
    test_encode_decode_secret()
    test_secret_store_roundtrip()
    print("test_secret_store ok")
