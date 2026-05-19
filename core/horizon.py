import math

import cv2
import numpy as np


def detect_angle(image_bgr: np.ndarray) -> float:
    """Return the CW rotation angle (degrees) needed to make the most central
    vertical line truly vertical. Returns 0.0 if no suitable line found.

    Looks for the dominant near-vertical line (doorframe, wall, person's body)
    whose midpoint is closest to the horizontal center of the frame, then
    measures how far it deviates from true vertical.
    """
    h, w = image_bgr.shape[:2]
    cx = w / 2.0
    cy = h / 2.0

    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)

    # Downscale for speed — keep the longest dimension ≤ 800px
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

    # In OpenCV HoughLines:
    #   theta = 0  → normal points +x   → line IS vertical
    #   theta = π/2 → normal points +y  → line is horizontal
    #   theta = π   → normal points -x  → line IS vertical (other side)
    # Near-vertical: theta < THRESH  or  theta > π - THRESH
    VERT_THRESH = math.radians(20)

    best: tuple | None = None
    best_dist = float("inf")

    for line in lines:
        rho, theta = float(line[0][0]), float(line[0][1])

        dev = min(theta, abs(theta - math.pi))
        if dev > VERT_THRESH:
            continue

        # x-position of this line at the vertical center of the (scaled) image
        cos_t = math.cos(theta)
        if abs(cos_t) < 1e-6:
            continue
        x_mid = (rho - (sch / 2.0) * math.sin(theta)) / cos_t

        dist = abs(x_mid - scx)
        if dist < best_dist:
            best_dist = dist
            best = (rho, theta)

    if best is None:
        return 0.0

    _, theta = best

    # Deviation of this line from true vertical (theta = 0 or π)
    # theta in [0, π/2): deviation = theta           (top leans left → need CW correction)
    # theta in (π/2, π]: deviation = theta - π       (top leans right → need CCW = negative CW)
    if theta <= math.pi / 2:
        deviation = math.degrees(theta)
    else:
        deviation = math.degrees(theta - math.pi)

    return 0.0 if abs(deviation) < 0.2 else round(deviation, 2)
