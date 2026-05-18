from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np

try:
    import mediapipe as mp
    _MP_AVAILABLE = True
except ImportError:
    _MP_AVAILABLE = False

# MediaPipe face mesh landmark indices
_LEFT_EYE = [362, 385, 387, 263, 373, 380]
_RIGHT_EYE = [33, 160, 158, 133, 153, 144]
_MOUTH_LEFT = 61
_MOUTH_RIGHT = 291
_MOUTH_TOP = 13
_MOUTH_BOTTOM = 14
_UPPER_LIP = 0
_LOWER_LIP = 17

EAR_OPEN = 0.22
EAR_BLINK_MID = 0.15
SMILE_THRESHOLD = 0.38


@dataclass
class FaceResult:
    face_count: int = 0
    dominant_eye_ar: float = 0.0
    dominant_left_ear: float = 0.0
    dominant_right_ear: float = 0.0
    dominant_smile: float = 0.0
    dominant_face_area: float = 0.0
    eyes_open: bool = True
    is_mid_blink: bool = False
    is_smiling: bool = False
    eyes_closed_aesthetic: bool = False
    has_faces: bool = False


def _ear(lm, indices, w, h) -> float:
    pts = [(lm[i].x * w, lm[i].y * h) for i in indices]
    A = np.linalg.norm(np.subtract(pts[1], pts[5]))
    B = np.linalg.norm(np.subtract(pts[2], pts[4]))
    C = np.linalg.norm(np.subtract(pts[0], pts[3]))
    return (A + B) / (2.0 * C) if C > 0 else 0.0


def _smile_score(lm, w, h) -> float:
    ml = np.array([lm[_MOUTH_LEFT].x * w, lm[_MOUTH_LEFT].y * h])
    mr = np.array([lm[_MOUTH_RIGHT].x * w, lm[_MOUTH_RIGHT].y * h])
    mt = np.array([lm[_UPPER_LIP].x * w, lm[_UPPER_LIP].y * h])
    mb = np.array([lm[_LOWER_LIP].x * w, lm[_LOWER_LIP].y * h])

    xs = [l.x for l in lm]
    face_w = max(xs) - min(xs)
    mouth_w = np.linalg.norm(mr - ml)
    mouth_h = np.linalg.norm(mb - mt)

    if face_w <= 0:
        return 0.0

    raw = (mouth_w / face_w) * 1.8 - 0.5 + mouth_h * 0.3
    return max(0.0, min(1.0, raw))


def _face_area(lm) -> float:
    xs = [l.x for l in lm]
    ys = [l.y for l in lm]
    return (max(xs) - min(xs)) * (max(ys) - min(ys))


class FaceAnalyzer:
    def __init__(self):
        self._mesh = None

    def _get_mesh(self):
        if not _MP_AVAILABLE:
            return None
        if self._mesh is None:
            mp_fm = mp.solutions.face_mesh
            self._mesh = mp_fm.FaceMesh(
                static_image_mode=True,
                max_num_faces=10,
                refine_landmarks=True,
                min_detection_confidence=0.5,
            )
        return self._mesh

    def analyze(self, frame_bgr: np.ndarray) -> FaceResult:
        mesh = self._get_mesh()
        if mesh is None:
            return FaceResult()

        h, w = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        results = mesh.process(rgb)

        if not results.multi_face_landmarks:
            return FaceResult()

        face_count = len(results.multi_face_landmarks)
        faces = []
        for face_lm in results.multi_face_landmarks:
            lm = face_lm.landmark
            lear = _ear(lm, _LEFT_EYE, w, h)
            rear = _ear(lm, _RIGHT_EYE, w, h)
            avg_ear = (lear + rear) / 2.0
            smile = _smile_score(lm, w, h)
            area = _face_area(lm)
            faces.append((area, avg_ear, lear, rear, smile))

        faces.sort(key=lambda x: x[0], reverse=True)
        dom_area, dom_ear, dom_lear, dom_rear, dom_smile = faces[0]

        eyes_open = dom_ear > EAR_OPEN
        is_mid_blink = EAR_BLINK_MID <= dom_ear <= EAR_OPEN
        eyes_closed = dom_ear < EAR_BLINK_MID
        eyes_closed_aesthetic = eyes_closed and face_count <= 2

        return FaceResult(
            face_count=face_count,
            dominant_eye_ar=dom_ear,
            dominant_left_ear=dom_lear,
            dominant_right_ear=dom_rear,
            dominant_smile=dom_smile,
            dominant_face_area=dom_area,
            eyes_open=eyes_open,
            is_mid_blink=is_mid_blink,
            is_smiling=dom_smile > SMILE_THRESHOLD,
            eyes_closed_aesthetic=eyes_closed_aesthetic,
            has_faces=True,
        )

    def has_faces(self, frame_bgr: np.ndarray) -> bool:
        mesh = self._get_mesh()
        if mesh is None:
            return False
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        results = mesh.process(rgb)
        return bool(results.multi_face_landmarks)

    def cleanup(self):
        if self._mesh is not None:
            self._mesh.close()
            self._mesh = None


def is_available() -> bool:
    return _MP_AVAILABLE
