import json
import keyring
from pathlib import Path

_CONFIG_DIR = Path.home() / ".frameable"
_CONFIG_FILE = _CONFIG_DIR / "config.json"
_KEYRING_SERVICE = "Frameable"

_DEFAULTS = {
    "last_output_dir": str(Path.home()),
    "auto_frames_per_sec": 8,
    "blur_mix_pct": 5,
    "sample_mode": "smart",
    "output_mode": "auto",
    "exact_count": 50,
    "subfolder_per_video": True,
    "google_api_usage": {},
}


def _ensure_dir():
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load() -> dict:
    _ensure_dir()
    if _CONFIG_FILE.exists():
        try:
            data = json.loads(_CONFIG_FILE.read_text())
            return {**_DEFAULTS, **data}
        except Exception:
            pass
    return dict(_DEFAULTS)


def save(config: dict):
    _ensure_dir()
    _CONFIG_FILE.write_text(json.dumps(config, indent=2))


def get_api_key(name: str) -> str | None:
    try:
        return keyring.get_password(_KEYRING_SERVICE, name)
    except Exception:
        return None


def set_api_key(name: str, value: str):
    try:
        keyring.set_password(_KEYRING_SERVICE, name, value)
    except Exception:
        pass


def delete_api_key(name: str):
    try:
        keyring.delete_password(_KEYRING_SERVICE, name)
    except Exception:
        pass
