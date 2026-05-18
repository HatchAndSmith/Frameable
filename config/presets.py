import json
from pathlib import Path
from typing import Optional

_PRESETS_FILE = Path.home() / ".frameable" / "presets.json"

PRESET_KEYS = (
    "output_mode",
    "exact_count",
    "blur_mix_pct",
    "auto_frames_per_sec",
    "subfolder_per_video",
)

BUILT_IN: dict[str, dict] = {
    "Wedding / Events": {
        "output_mode": "auto",
        "exact_count": 100,
        "blur_mix_pct": 5,
        "auto_frames_per_sec": 6,
        "subfolder_per_video": True,
    },
    "Portrait Session": {
        "output_mode": "auto",
        "exact_count": 60,
        "blur_mix_pct": 3,
        "auto_frames_per_sec": 8,
        "subfolder_per_video": True,
    },
    "Action / Sports": {
        "output_mode": "auto",
        "exact_count": 80,
        "blur_mix_pct": 8,
        "auto_frames_per_sec": 4,
        "subfolder_per_video": True,
    },
    "Quick Cull": {
        "output_mode": "exact",
        "exact_count": 20,
        "blur_mix_pct": 0,
        "auto_frames_per_sec": 15,
        "subfolder_per_video": False,
    },
}


def _load_user() -> dict[str, dict]:
    if _PRESETS_FILE.exists():
        try:
            return json.loads(_PRESETS_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_user(data: dict):
    _PRESETS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _PRESETS_FILE.write_text(json.dumps(data, indent=2))


def all_presets() -> dict[str, dict]:
    merged = dict(BUILT_IN)
    merged.update(_load_user())
    return merged


def names() -> list[str]:
    return list(all_presets().keys())


def get(name: str) -> Optional[dict]:
    return all_presets().get(name)


def save(name: str, settings: dict):
    user = _load_user()
    user[name] = {k: settings[k] for k in PRESET_KEYS if k in settings}
    _save_user(user)


def delete(name: str):
    if name in BUILT_IN:
        return  # never delete built-ins
    user = _load_user()
    user.pop(name, None)
    _save_user(user)


def is_built_in(name: str) -> bool:
    return name in BUILT_IN
