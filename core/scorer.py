import cv2
import numpy as np

from core.face_analyzer import FaceResult

# Scoring weights (must sum to 1.0)
W_SHARP = 0.25
W_EXPOSE = 0.15
W_FACE = 0.28
W_EXPR = 0.27
W_MOTION = 0.05

# Sharpness: Laplacian variance — tuned for typical video resolutions
SHARP_SCALE = 400.0
BLUR_THRESHOLD = 0.08  # below = eligible as aesthetic blur


def score_sharpness(gray: np.ndarray) -> float:
    lap = cv2.Laplacian(gray, cv2.CV_64F).var()
    return min(1.0, lap / SHARP_SCALE)


def score_exposure(frame_bgr: np.ndarray) -> float:
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).flatten()
    hist = hist / hist.sum()
    blown = hist[245:].sum()
    crushed = hist[:10].sum()
    good = hist[40:220].sum()
    raw = good - blown * 2.5 - crushed * 1.5
    return max(0.0, min(1.0, raw + 0.15))


def score_motion(frame_bgr: np.ndarray, prev_bgr: np.ndarray | None) -> float:
    if prev_bgr is None:
        return 1.0
    g1 = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    g2 = cv2.cvtColor(prev_bgr, cv2.COLOR_BGR2GRAY)
    diff = cv2.absdiff(g1, g2).mean()
    return max(0.0, 1.0 - diff / 45.0)


def score_face_quality(fr: FaceResult) -> float:
    if not fr.has_faces:
        return 0.45
    s = 0.4
    s += min(0.35, fr.dominant_face_area * 3.5)
    if fr.eyes_open:
        s += 0.25
    return min(1.0, s)


def score_expression(fr: FaceResult) -> float:
    if not fr.has_faces:
        return 0.45

    # Mid-blink is never good
    if fr.is_mid_blink:
        return 0.05

    # Eyes closed in a group is unusable
    if not fr.eyes_open and not fr.eyes_closed_aesthetic:
        return 0.02

    # Genuine smile + eyes open (Duchenne) — top tier
    if fr.is_smiling and fr.eyes_open:
        return 1.0

    # Smile, eyes not fully open (looking away, blinking-but-smiling)
    if fr.is_smiling:
        return 0.72

    # Eyes closed — aesthetic in small group
    if fr.eyes_closed_aesthetic:
        return 0.38

    # Eyes open, neutral — solid pick
    if fr.eyes_open:
        return 0.55

    return 0.3


def apply_cloud_boost(base_score: float, cloud_data: dict) -> float:
    if not cloud_data:
        return base_score

    boost = 0.0
    joy = cloud_data.get("cloud_joy", 0.0)
    sorrow = cloud_data.get("cloud_sorrow", 0.0)
    surprise = cloud_data.get("cloud_surprise", 0.0)
    blurred = cloud_data.get("cloud_blurred", 0.0)
    under = cloud_data.get("cloud_under_exposed", 0.0)
    aesthetic = cloud_data.get("cloud_aesthetic", 0.0)

    # Expression boosts (cloud confirms offline scoring)
    boost += joy * 0.12
    boost += sorrow * 0.08
    boost += surprise * 0.07

    # Quality penalties from cloud
    boost -= blurred * 0.15
    boost -= under * 0.10

    # NIMA aesthetic score
    if aesthetic > 0:
        nima_delta = (aesthetic - 0.5) * 0.2
        boost += nima_delta

    return max(0.0, min(1.0, base_score + boost))


def score_candidate(frame_bgr: np.ndarray, face_result: FaceResult,
                    prev_bgr: np.ndarray | None = None,
                    cloud_data: dict | None = None) -> tuple[float, dict]:
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    sharpness = score_sharpness(gray)
    exposure = score_exposure(frame_bgr)
    motion = score_motion(frame_bgr, prev_bgr)
    face_q = score_face_quality(face_result)
    expression = score_expression(face_result)

    raw = (W_SHARP * sharpness + W_EXPOSE * exposure + W_MOTION * motion
           + W_FACE * face_q + W_EXPR * expression)

    final = apply_cloud_boost(raw, cloud_data or {})

    flags = {
        "sharpness": sharpness,
        "exposure": exposure,
        "motion": motion,
        "face_quality": face_q,
        "expression": expression,
        "is_blurry": sharpness < BLUR_THRESHOLD,
    }
    return final, flags
