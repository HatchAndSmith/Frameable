import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from core import extractor, scene_detect, scorer, exporter
from core.cloud_scorer import CloudScorer
from core.extractor import FrameCandidate, VideoInfo
from core.face_analyzer import FaceAnalyzer
from core.scorer import BLUR_THRESHOLD


@dataclass
class ProcessingResult:
    video_path: Path
    saved_paths: list[Path] = field(default_factory=list)
    frame_count: int = 0
    error: Optional[str] = None


Callback = Callable[[str, float, int], None]  # (filename, progress 0-1, frames_so_far)


def _auto_count(duration_sec: float, secs_per_frame: int = 8) -> int:
    return max(1, int(duration_sec / secs_per_frame))


def _distribute_counts(videos: list[VideoInfo], total: int) -> dict[Path, int]:
    total_dur = sum(v.duration for v in videos) or 1
    counts = {}
    allocated = 0
    for i, v in enumerate(videos[:-1]):
        n = max(1, round(total * v.duration / total_dur))
        counts[v.path] = n
        allocated += n
    counts[videos[-1].path] = max(1, total - allocated)
    return counts


def process_video(
    video_path: Path,
    target_count: int,
    output_dir: Path,
    blur_pct: int,
    cloud_scorer: Optional[CloudScorer],
    subfolder: bool = True,
    progress_cb: Optional[Callback] = None,
    stop_event: Optional[threading.Event] = None,
) -> ProcessingResult:
    result = ProcessingResult(video_path=video_path)
    name = video_path.name

    def _progress(p: float, frames: int = 0):
        if progress_cb:
            progress_cb(name, p, frames)

    def _stopped() -> bool:
        return stop_event is not None and stop_event.is_set()

    try:
        info = extractor.get_video_info(video_path)
        _progress(0.02)

        scenes = scene_detect.detect_scenes(video_path, info.duration)
        _progress(0.06)

        if _stopped():
            return result

        # --- Smart sampling ---
        face_analyzer = FaceAnalyzer()
        coarse = extractor.extract_coarse(video_path, info, interval=0.5)
        _progress(0.20)

        if _stopped():
            face_analyzer.cleanup()
            return result

        # Identify coarse frames with faces for fine-grained sampling
        face_timestamps = set()
        for i, c in enumerate(coarse):
            if face_analyzer.has_faces(c.image):
                face_timestamps.add(c.timestamp)
            if i % 20 == 0:
                _progress(0.20 + 0.12 * (i / max(len(coarse), 1)))

        if _stopped():
            face_analyzer.cleanup()
            return result

        # Fine pass around face timestamps
        fine = []
        for ts in face_timestamps:
            fine.extend(extractor.extract_window(video_path, info, ts, window=0.75))
        _progress(0.38)

        all_candidates = extractor.dedup_candidates(coarse + fine, min_gap=0.1)

        # --- Full scoring ---
        prev_frame: Optional[np.ndarray] = None
        for i, c in enumerate(all_candidates):
            if _stopped():
                face_analyzer.cleanup()
                return result

            face_result = face_analyzer.analyze(c.image)
            c.face_count = face_result.face_count

            # Cloud score only faces (saves credits) and only every 3rd candidate
            cloud_data = {}
            if (cloud_scorer and cloud_scorer.any_available
                    and face_result.has_faces and i % 3 == 0):
                cloud_data = cloud_scorer.score_frame(c.image)

            final_score, flags = scorer.score_candidate(
                c.image, face_result, prev_bgr=prev_frame, cloud_data=cloud_data
            )
            c.score = final_score
            c.cloud_data = cloud_data
            c.sharpness = flags["sharpness"]
            prev_frame = c.image

            if i % 15 == 0:
                _progress(0.38 + 0.45 * (i / max(len(all_candidates), 1)), len(result.saved_paths))

        face_analyzer.cleanup()
        _progress(0.83)

        if not all_candidates:
            result.error = "No frames could be extracted."
            return result

        # --- Proportional selection per scene ---
        blur_count = max(0, round(target_count * blur_pct / 100))
        sharp_count = target_count - blur_count

        sharp_candidates = sorted(
            [c for c in all_candidates if c.sharpness >= BLUR_THRESHOLD],
            key=lambda x: x.score, reverse=True
        )
        blur_candidates = sorted(
            [c for c in all_candidates if c.sharpness < BLUR_THRESHOLD
             and c.face_count > 0],  # blur frames still need faces to be interesting
            key=lambda x: x.score, reverse=True
        )

        selected = _pick_proportional(sharp_candidates, scenes, sharp_count)
        blur_picks = blur_candidates[:blur_count]
        for c in blur_picks:
            c.is_aesthetic_blur = True

        final_picks = _spread_picks(selected + blur_picks)
        _progress(0.88)

        # --- Export ---
        sub_dir = (output_dir / video_path.stem) if subfolder else output_dir
        for i, c in enumerate(final_picks):
            if _stopped():
                return result
            saved = exporter.export_tiff(c.image, sub_dir, video_path.name, c.timestamp)
            result.saved_paths.append(saved)
            _progress(0.88 + 0.12 * (i / max(len(final_picks), 1)), len(result.saved_paths))

        result.frame_count = len(result.saved_paths)
        _progress(1.0, result.frame_count)

    except Exception as e:
        result.error = str(e)

    return result


def _pick_proportional(candidates: list[FrameCandidate],
                       scenes: list[tuple[float, float]],
                       total: int) -> list[FrameCandidate]:
    if not candidates or total <= 0:
        return []
    if len(candidates) <= total:
        return candidates

    total_dur = sum(e - s for s, e in scenes) or 1.0
    picks = []

    for scene_start, scene_end in scenes:
        quota = max(1, round(total * (scene_end - scene_start) / total_dur))
        in_scene = [c for c in candidates if scene_start <= c.timestamp < scene_end]
        in_scene.sort(key=lambda x: x.score, reverse=True)
        picks.extend(in_scene[:quota])

    # Top-up if proportional picked fewer
    if len(picks) < total:
        already = {id(c) for c in picks}
        remainder = sorted(
            [c for c in candidates if id(c) not in already],
            key=lambda x: x.score, reverse=True
        )
        picks.extend(remainder[:total - len(picks)])

    return picks[:total]


def _spread_picks(picks: list[FrameCandidate]) -> list[FrameCandidate]:
    return sorted(picks, key=lambda x: x.timestamp)


def process_batch(
    videos: list[Path],
    output_dir: Path,
    output_mode: str,
    exact_count: int,
    secs_per_frame: int,
    blur_pct: int,
    cloud_scorer: Optional[CloudScorer],
    subfolder: bool = True,
    progress_cb: Optional[Callable] = None,
    stop_event: Optional[threading.Event] = None,
) -> list[ProcessingResult]:
    infos = []
    for p in videos:
        try:
            infos.append(extractor.get_video_info(p))
        except Exception:
            infos.append(None)

    valid_infos = [i for i in infos if i is not None]

    if output_mode == "auto":
        counts = {v.path: _auto_count(v.duration, secs_per_frame) for v in valid_infos}
    else:
        counts = _distribute_counts(valid_infos, exact_count) if valid_infos else {}

    results = []
    for p, info in zip(videos, infos):
        if stop_event and stop_event.is_set():
            break
        if info is None:
            results.append(ProcessingResult(video_path=p, error="Could not read video."))
            continue
        target = counts.get(p, 1)
        r = process_video(p, target, output_dir, blur_pct, cloud_scorer,
                          subfolder=subfolder,
                          progress_cb=progress_cb, stop_event=stop_event)
        results.append(r)

    return results
