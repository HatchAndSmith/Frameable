from pathlib import Path

try:
    from scenedetect import detect, AdaptiveDetector, SceneManager
    from scenedetect.video_splitter import split_video_ffmpeg
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False

import logging as _logging
_logging.getLogger("scenedetect").setLevel(_logging.CRITICAL + 1)


def detect_scenes(path: Path, duration: float) -> list[tuple[float, float]]:
    if not _AVAILABLE:
        return [(0.0, duration)]
    try:
        scenes = detect(str(path), AdaptiveDetector())
        if not scenes:
            return [(0.0, duration)]
        result = []
        for start, end in scenes:
            result.append((start.get_seconds(), end.get_seconds()))
        return result
    except Exception:
        return [(0.0, duration)]


def is_available() -> bool:
    return _AVAILABLE
