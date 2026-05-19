import math

import cv2
import numpy as np


def detect_angle(image_bgr: np.ndarray) -> float:
    """Return the tilt angle (degrees) needed to straighten the horizon.

    Positive values = image is tilted clockwise (rotate CCW to correct).
    Returns 0.0 if no clear horizontal lines detected or tilt < 0.2°.
    """
    h, w = image_bgr.shape[:2]
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)

    # Downscale for speed
    scale = min(1.0, 800.0 / max(w, h))
    if scale < 1.0:
        small = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    else:
        small = gray

    edges = cv2.Canny(small, 50, 150, apertureSize=3)
    lines = cv2.HoughLines(edges, 1, math.pi / 180, threshold=60)

    if lines is None:
        return 0.0

    angles = []
    for line in lines:
        theta = float(line[0][1])
        angle_deg = math.degrees(theta) - 90.0
        if abs(angle_deg) <= 10.0:
            angles.append(angle_deg)

    if not angles:
        return 0.0

    angle = float(np.median(angles))
    return 0.0 if abs(angle) < 0.2 else round(angle, 2)
