from __future__ import annotations

from typing import TYPE_CHECKING

import cv2
import numpy as np

if TYPE_CHECKING:
    from core.extractor import FrameCandidate

_IMAGEHASH_AVAILABLE = False
try:
    import imagehash
    from PIL import Image as _PILImage
    _IMAGEHASH_AVAILABLE = True
except ImportError:
    pass

DEFAULT_THRESHOLD = 8   # Hamming distance — lower = stricter (more unique frames)


def _phash(frame_bgr: np.ndarray):
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    pil = _PILImage.fromarray(rgb)
    return imagehash.phash(pil)


def _fallback_hash(frame_bgr: np.ndarray) -> np.ndarray:
    """Lightweight 8x8 DCT-based hash using only numpy/cv2 (no imagehash)."""
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32)
    dct = cv2.dct(small)
    top = dct[:8, :8].flatten()
    return top > top.mean()


def _fallback_distance(h1: np.ndarray, h2: np.ndarray) -> int:
    return int(np.sum(h1 != h2))


def deduplicate(
    candidates: list[FrameCandidate],
    threshold: int = DEFAULT_THRESHOLD,
) -> list[FrameCandidate]:
    """Remove perceptually near-duplicate frames from an already-ranked list.

    Candidates should be passed in priority order (best first); the first
    occurrence of a visual cluster is kept, duplicates are dropped.
    """
    if not candidates:
        return candidates

    kept: list[FrameCandidate] = []

    if _IMAGEHASH_AVAILABLE:
        hashes = []
        for c in candidates:
            h = _phash(c.image)
            if all(abs(h - existing) >= threshold for existing in hashes):
                kept.append(c)
                hashes.append(h)
    else:
        hashes = []
        for c in candidates:
            h = _fallback_hash(c.image)
            if all(_fallback_distance(h, existing) >= threshold for existing in hashes):
                kept.append(c)
                hashes.append(h)

    return kept


def is_available() -> bool:
    return _IMAGEHASH_AVAILABLE
