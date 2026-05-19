from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.extractor import FrameCandidate


def generate(candidate: FrameCandidate) -> list[str]:
    kws: list[str] = []
    img = candidate.image
    h, w = img.shape[:2]

    # Orientation
    if w > h * 1.05:
        kws += ["horizontal", "landscape"]
    elif h > w * 1.05:
        kws += ["vertical", "portrait"]
    else:
        kws.append("square")

    # People count
    fc = candidate.face_count
    if fc == 0:
        kws.append("no people")
    elif fc == 1:
        kws += ["1 person", "portrait"]
    elif fc == 2:
        kws.append("2 people")
    elif fc == 3:
        kws.append("3 people")
    elif fc <= 6:
        kws += [f"{fc} people", "small group"]
    else:
        kws += [f"{fc} people", "large group", "crowd"]

    # Expression
    if fc > 0:
        if candidate.is_smiling:
            kws.append("smiling")
            if candidate.smile_score > 0.65:
                kws.append("big smile")
        if not candidate.eyes_open:
            kws.append("eyes closed")

    # Subject size (face area fraction of frame)
    if fc > 0 and candidate.face_area > 0:
        if candidate.face_area > 0.20:
            kws.append("close-up portrait")
        elif candidate.face_area > 0.06:
            kws.append("medium portrait")

    # Technical quality
    from core.scorer import BLUR_THRESHOLD
    if candidate.is_aesthetic_blur:
        kws.append("motion blur")
    elif candidate.sharpness < BLUR_THRESHOLD:
        kws.append("soft focus")
    else:
        kws.append("sharp")

    if candidate.exposure < 0.3:
        kws.append("dark")
    elif candidate.exposure > 0.85:
        kws.append("bright")

    return kws
