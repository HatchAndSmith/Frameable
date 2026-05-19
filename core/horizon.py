import math

import cv2
import numpy as np


def detect_angle(image_bgr: np.ndarray) -> float:
    """Return the CW rotation angle (degrees) to straighten the frame.

    Strategy:
      1. Find the near-vertical line whose midpoint is closest to the
         horizontal centre (doorframe, wall, person's body).
      2. If no near-vertical lines exist, fall back to the dominant
         near-horizontal line (sky/ground horizon).
      3. Return 0.0 if neither strategy finds anything usable.
    """
    h, w = image_bgr.shape[:2]
    cx = w / 2.0

    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)

    scale = min(1.0, 800.0 / max(w, h))
    if scale < 1.0:
        small = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        scx = cx * scale
        sch = h * scale
    else:
        small = gray
        scx = cx
        sch = float(h)

    edges = cv2.Canny(small, 50, 150, apertureSize=3)
    lines = cv2.HoughLines(edges, 1, math.pi / 180, threshold=60)

    if lines is None:
        return 0.0

    # ── Pass 1: centermost near-vertical line ──────────────────────────────
    # theta ≈ 0 or ≈ π  →  vertical line
    VERT_THRESH = math.radians(20)

    best_vert: tuple | None = None
    best_dist = float("inf")

    for line in lines:
        rho, theta = float(line[0][0]), float(line[0][1])
        dev = min(theta, abs(theta - math.pi))
        if dev > VERT_THRESH:
            continue
        cos_t = math.cos(theta)
        if abs(cos_t) < 1e-6:
            continue
        x_mid = (rho - (sch / 2.0) * math.sin(theta)) / cos_t
        dist = abs(x_mid - scx)
        if dist < best_dist:
            best_dist = dist
            best_vert = (rho, theta)

    if best_vert is not None:
        _, theta = best_vert
        deviation = math.degrees(theta) if theta <= math.pi / 2 else math.degrees(theta - math.pi)
        return 0.0 if abs(deviation) < 0.2 else round(deviation, 2)

    # ── Pass 2: fallback — dominant near-horizontal line (horizon) ─────────
    # theta ≈ π/2  →  horizontal line
    HORIZ_THRESH = math.radians(10)

    horiz_angles: list[float] = []
    for line in lines:
        _, theta = float(line[0][0]), float(line[0][1])
        dev = abs(theta - math.pi / 2)
        if dev <= HORIZ_THRESH:
            # Deviation from perfect horizontal in degrees
            horiz_angles.append(math.degrees(theta - math.pi / 2))

    if not horiz_angles:
        return 0.0

    # A horizon tilted by +d° requires a -d° CW correction (rotate CCW)
    tilt = float(np.median(horiz_angles))
    correction = -tilt
    return 0.0 if abs(correction) < 0.2 else round(correction, 2)
