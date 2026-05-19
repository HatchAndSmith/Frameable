import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from core import dedup, extractor, scene_detect, scorer, exporter
from core.cloud_scorer import CloudScorer
from core.extractor import FrameCandidate, VideoInfo
from core.face_analyzer import FaceAnalyzer
from core.log import get as get_log
from core.scorer import BLUR_THRESHOLD

_log = get_log("processor")


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
    face_analyzer: Optional[FaceAnalyzer] = None,
    write_xmp: bool = False,
    write_angle: bool = False,
) -> ProcessingResult:
    result = ProcessingResult(video_path=video_path)
    name = video_path.name

    def _progress(p: float, frames: int = 0):
        if progress_cb:
            progress_cb(name, p, frames)

    def _stopped() -> bool:
        return stop_event is not None and stop_event.is_set()

    _own_analyzer = face_analyzer is None
    if _own_analyzer:
        face_analyzer = FaceAnalyzer()
    try:
        _log.info("Processing %s  target=%d", name, target_count)
        info = extractor.get_video_info(video_path)
        _log.info("  %dx%d  %.1ffps  %.1fs  codec=%s",
                  info.width, info.height, info.fps, info.duration, info.codec)
        _progress(0.02)

        scenes = scene_detect.detect_scenes(video_path, info.duration)
        _log.info("  %d scene(s) detected", len(scenes))
        _progress(0.06)

        if _stopped():
            return result

        # --- Smart sampling ---
        coarse = extractor.extract_coarse(video_path, info, interval=0.5)
        _log.info("  coarse pass: %d candidates", len(coarse))
        _progress(0.20)

        if not coarse:
            result.error = "No frames could be extracted — file may be corrupt or codec unsupported."
            _log.warning("  no coarse frames for %s", name)
            return result

        if _stopped():
            return result

        # Identify coarse frames with faces for fine-grained sampling
        face_timestamps = set()
        for i, c in enumerate(coarse):
            try:
                if face_analyzer.has_faces(c.image):
                    face_timestamps.add(c.timestamp)
            except Exception:
                pass
            if i % 20 == 0:
                _progress(0.20 + 0.12 * (i / max(len(coarse), 1)))

        _log.info("  %d face timestamp(s) found for fine pass", len(face_timestamps))

        if _stopped():
            return result

        # Fine pass around face timestamps
        fine = []
        for ts in face_timestamps:
            fine.extend(extractor.extract_window(video_path, info, ts, window=0.75))
        _log.info("  fine pass: %d additional candidates", len(fine))
        _progress(0.38)

        all_candidates = extractor.dedup_candidates(coarse + fine, min_gap=0.1)
        _log.info("  total deduplicated candidates: %d", len(all_candidates))

        # --- Full scoring ---
        prev_frame: Optional[np.ndarray] = None
        for i, c in enumerate(all_candidates):
            if _stopped():
                return result

            try:
                face_result = face_analyzer.analyze(c.image)
            except Exception as exc:
                _log.debug("Face analysis failed frame %d: %s", i, exc)
                from core.face_analyzer import FaceResult
                face_result = FaceResult()

            c.face_count = face_result.face_count
            c.is_smiling = face_result.is_smiling
            c.smile_score = face_result.dominant_smile
            c.eyes_open = face_result.eyes_open
            c.face_area = face_result.dominant_face_area

            # Cloud score only faces (saves credits) and only every 3rd candidate
            cloud_data = {}
            if (cloud_scorer and cloud_scorer.any_available
                    and face_result.has_faces and i % 3 == 0):
                try:
                    cloud_data = cloud_scorer.score_frame(c.image)
                except Exception as exc:
                    _log.debug("Cloud scoring failed frame %d: %s", i, exc)

            try:
                final_score, flags = scorer.score_candidate(
                    c.image, face_result, prev_bgr=prev_frame, cloud_data=cloud_data
                )
            except Exception as exc:
                _log.debug("Scoring failed frame %d: %s", i, exc)
                final_score, flags = 0.0, {"sharpness": 0.0, "is_blurry": True}

            c.score = final_score
            c.cloud_data = cloud_data
            c.sharpness = flags.get("sharpness", 0.0)
            c.exposure = flags.get("exposure", 0.5)
            prev_frame = c.image

            if i % 15 == 0:
                _progress(0.38 + 0.45 * (i / max(len(all_candidates), 1)),
                          len(result.saved_paths))

        _progress(0.83)

        # --- Proportional selection per scene ---
        blur_count  = max(0, round(target_count * blur_pct / 100))
        sharp_count = max(1, target_count - blur_count)

        sharp_candidates = sorted(
            [c for c in all_candidates if c.sharpness >= BLUR_THRESHOLD],
            key=lambda x: x.score, reverse=True,
        )
        blur_candidates = sorted(
            [c for c in all_candidates
             if c.sharpness < BLUR_THRESHOLD and c.face_count > 0],
            key=lambda x: x.score, reverse=True,
        )

        # Fall back to all candidates if no sharp ones (e.g. very shaky footage)
        if not sharp_candidates:
            _log.warning("  no sharp candidates — using all candidates for selection")
            sharp_candidates = sorted(all_candidates, key=lambda x: x.score, reverse=True)

        selected    = _pick_proportional(sharp_candidates, scenes, sharp_count)
        blur_picks  = blur_candidates[:blur_count]
        for c in blur_picks:
            c.is_aesthetic_blur = True

        # Dedup: remove near-identical frames from final selection
        sharp_deduped = dedup.deduplicate(selected)
        blur_deduped  = dedup.deduplicate(blur_picks)
        final_picks   = _spread_picks(sharp_deduped + blur_deduped)

        _log.info("  selected %d sharp + %d blur = %d total",
                  len(sharp_deduped), len(blur_deduped), len(final_picks))
        _progress(0.88)

        if not final_picks:
            result.error = "Scoring produced no selectable frames."
            _log.warning("  no final picks for %s", name)
            return result

        # --- Export ---
        sub_dir = (output_dir / video_path.stem) if subfolder else output_dir
        for i, c in enumerate(final_picks):
            if _stopped():
                return result
            try:
                kws = None
                angle = 0.0
                if write_xmp:
                    from core import keywords as kw_mod
                    kws = kw_mod.generate(c)
                    if write_angle:
                        from core import horizon as hz_mod
                        angle = hz_mod.detect_angle(c.image)
                saved = exporter.export_tiff(
                    c.image, sub_dir, video_path.name, c.timestamp,
                    keywords=kws, crop_angle=angle,
                    write_xmp=write_xmp, write_angle=write_angle,
                )
                result.saved_paths.append(saved)
            except Exception as exc:
                _log.error("  export failed frame %.2fs: %s", c.timestamp, exc)
            _progress(0.88 + 0.12 * (i / max(len(final_picks), 1)),
                      len(result.saved_paths))

        result.frame_count = len(result.saved_paths)
        _log.info("  done: %d frames saved to %s", result.frame_count, sub_dir)
        _progress(1.0, result.frame_count)

    except Exception as exc:
        _log.exception("Unhandled error processing %s", name)
        result.error = str(exc)
    finally:
        if _own_analyzer:
            face_analyzer.cleanup()

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
    write_xmp: bool = False,
    write_angle: bool = False,
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

    shared_analyzer = FaceAnalyzer()
    results = []
    try:
        for p, info in zip(videos, infos):
            if stop_event and stop_event.is_set():
                break
            if info is None:
                results.append(ProcessingResult(video_path=p, error="Could not read video."))
                continue
            target = counts.get(p, 1)
            r = process_video(p, target, output_dir, blur_pct, cloud_scorer,
                              subfolder=subfolder,
                              progress_cb=progress_cb, stop_event=stop_event,
                              face_analyzer=shared_analyzer,
                              write_xmp=write_xmp, write_angle=write_angle)
            results.append(r)
    finally:
        shared_analyzer.cleanup()

    return results
