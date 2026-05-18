import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import cv2
import imageio_ffmpeg
import numpy as np

SUPPORTED_EXTENSIONS = {
    ".mp4", ".mov", ".m4v", ".mkv", ".avi", ".mts",
    ".m2ts", ".wmv", ".webm", ".flv", ".3gp",
    ".mxf", ".r3d", ".braw",
}


@dataclass
class VideoInfo:
    path: Path
    width: int
    height: int
    fps: float
    duration: float
    total_frames: int
    codec: str


@dataclass
class FrameCandidate:
    timestamp: float
    frame_number: int
    image: np.ndarray
    score: float = 0.0
    cloud_data: dict = field(default_factory=dict)
    is_aesthetic_blur: bool = False
    sharpness: float = 0.0
    face_count: int = 0


_BRAW_NOTE = (
    "BRAW files require the Blackmagic RAW Player to be installed. "
    "Download free from blackmagicdesign.com/support"
)


def get_video_info(path: Path) -> VideoInfo:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        if path.suffix.lower() == ".braw":
            raise RuntimeError(f"{path.name}: {_BRAW_NOTE}")
        raise RuntimeError(f"Cannot open {path.name} — codec may not be supported.")

    fps    = cap.get(cv2.CAP_PROP_FPS) or 24.0
    total  = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
    codec  = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)]).strip()
    cap.release()

    if width == 0 or height == 0:
        if path.suffix.lower() == ".braw":
            raise RuntimeError(f"{path.name}: {_BRAW_NOTE}")
        raise RuntimeError(
            f"{path.name}: video dimensions are 0 — codec '{codec}' is not supported "
            "by your OpenCV build. Install the required codec or convert the file to H.264/MOV."
        )

    duration = total / fps if fps > 0 else 0
    return VideoInfo(path=path, width=width, height=height, fps=fps,
                     duration=duration, total_frames=total, codec=codec)


def _ffmpeg_exe() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


def _iter_frames_ffmpeg(path: Path, width: int, height: int,
                        fps: float = 30.0,
                        start: float = 0, end: float | None = None) -> Iterator[tuple[float, np.ndarray]]:
    cmd = [_ffmpeg_exe(), "-loglevel", "error"]
    if start > 0:
        cmd += ["-ss", str(start)]
    cmd += ["-i", str(path)]
    if end is not None:
        cmd += ["-t", str(end - start)]
    cmd += ["-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    # Use DEVNULL for stderr — leaving it as PIPE risks deadlock when the
    # OS pipe buffer fills on long stderr output from FFmpeg.
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    frame_size = width * height * 3
    frame_step = 1.0 / max(fps, 1.0)
    ts = start
    try:
        while True:
            raw = proc.stdout.read(frame_size)
            if len(raw) < frame_size:
                break
            frame = np.frombuffer(raw, np.uint8).reshape(height, width, 3).copy()
            yield ts, frame
            ts += frame_step
    finally:
        proc.stdout.close()
        proc.wait()


def extract_at_timestamps(path: Path, info: VideoInfo,
                          timestamps: list[float]) -> list[FrameCandidate]:
    candidates = []
    cap = cv2.VideoCapture(str(path))
    cap_ok = cap.isOpened()
    try:
        for ts in sorted(set(timestamps)):
            frame = None
            if cap_ok:
                cap.set(cv2.CAP_PROP_POS_MSEC, ts * 1000)
                ok, f = cap.read()
                if ok and f is not None and f.size > 0:
                    frame = f

            if frame is None:
                for _ffts, f in _iter_frames_ffmpeg(path, info.width, info.height,
                                                    fps=info.fps,
                                                    start=max(0, ts - 0.05),
                                                    end=ts + 0.05):
                    frame = f
                    break

            if frame is not None:
                fn = int(ts * info.fps)
                candidates.append(FrameCandidate(timestamp=ts, frame_number=fn, image=frame))
    finally:
        if cap_ok:
            cap.release()
    return candidates


def extract_coarse(path: Path, info: VideoInfo,
                   interval: float = 0.5) -> list[FrameCandidate]:
    if info.duration <= 0:
        return []
    timestamps = [i * interval for i in range(int(info.duration / interval) + 1)
                  if i * interval < info.duration]
    return extract_at_timestamps(path, info, timestamps)


def extract_window(path: Path, info: VideoInfo,
                   center_ts: float, window: float = 0.75) -> list[FrameCandidate]:
    fps = info.fps
    step = 1.0 / fps
    start = max(0, center_ts - window)
    end = min(info.duration, center_ts + window)
    timestamps = []
    t = start
    while t <= end:
        timestamps.append(round(t, 4))
        t += step
    return extract_at_timestamps(path, info, timestamps)


def dedup_candidates(candidates: list[FrameCandidate],
                     min_gap: float = 0.1) -> list[FrameCandidate]:
    seen: dict[int, FrameCandidate] = {}
    for c in candidates:
        bucket = int(c.timestamp / min_gap)
        if bucket not in seen:
            seen[bucket] = c
    return sorted(seen.values(), key=lambda x: x.timestamp)
