"""
Smoke tests for the core pipeline — no video file or UI needed.

Run:  python test_smoke.py
Pass: all lines print OK
Fail: prints what broke and exits non-zero
"""

import sys
import traceback
import numpy as np

PASS = 0
FAIL = 0


def test(name: str, fn):
    global PASS, FAIL
    try:
        fn()
        print(f"  OK  {name}")
        PASS += 1
    except Exception:
        print(f"  FAIL  {name}")
        traceback.print_exc()
        FAIL += 1


# ── Synthetic frame helpers ────────────────────────────────────────────────

def sharp_frame(h=480, w=640):
    import cv2
    base = np.zeros((h, w, 3), dtype=np.uint8)
    for i in range(h):
        base[i] = [int(255 * i / h), 120, 200]
    return base


def blurry_frame(h=480, w=640):
    import cv2
    return cv2.GaussianBlur(sharp_frame(h, w), (31, 31), 0)


def dark_frame(h=480, w=640):
    return np.zeros((h, w, 3), dtype=np.uint8)


def bright_frame(h=480, w=640):
    return np.full((h, w, 3), 255, dtype=np.uint8)


# ── Tests ──────────────────────────────────────────────────────────────────

def test_sharpness():
    import cv2
    from core.scorer import score_sharpness
    s = sharp_frame()
    b = blurry_frame()
    gs = cv2.cvtColor(s, cv2.COLOR_BGR2GRAY)
    gb = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)
    ss = score_sharpness(gs)
    sb = score_sharpness(gb)
    assert ss > sb, f"sharp ({ss:.3f}) should beat blurry ({sb:.3f})"
    assert 0.0 <= ss <= 1.0
    assert 0.0 <= sb <= 1.0


def test_exposure():
    from core.scorer import score_exposure
    normal = sharp_frame()
    dark   = dark_frame()
    bright = bright_frame()
    sn = score_exposure(normal)
    sd = score_exposure(dark)
    sb = score_exposure(bright)
    assert sn > sd, f"normal ({sn:.3f}) should beat dark ({sd:.3f})"
    assert sn > sb, f"normal ({sn:.3f}) should beat bright ({sb:.3f})"
    assert all(0.0 <= s <= 1.0 for s in (sn, sd, sb))


def test_motion():
    from core.scorer import score_motion
    f1 = sharp_frame()
    f2 = sharp_frame()  # identical
    noisy = f1.copy()
    noisy[100:200, 100:200] = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
    still  = score_motion(f1, f2)
    moving = score_motion(noisy, f1)
    assert still > moving, f"still ({still:.3f}) should beat moving ({moving:.3f})"
    assert still == 1.0 or still > 0.95  # near-identical frames
    assert 0.0 <= moving <= 1.0


def test_face_result_defaults():
    from core.face_analyzer import FaceResult
    fr = FaceResult()
    assert fr.has_faces is False
    assert fr.face_count == 0


def test_score_no_face():
    from core.face_analyzer import FaceResult
    from core.scorer import score_candidate
    frame = sharp_frame()
    fr = FaceResult()
    score, flags = score_candidate(frame, fr)
    assert 0.0 <= score <= 1.0
    assert "sharpness" in flags
    assert "is_blurry" in flags


def test_expression_scoring():
    from core.face_analyzer import FaceResult
    from core.scorer import score_expression

    # Genuine smile, eyes open — top tier
    fr_smile = FaceResult(has_faces=True, eyes_open=True, is_smiling=True,
                          is_mid_blink=False, eyes_closed_aesthetic=False, face_count=1)
    # Eyes closed, 3 people — should be penalised
    fr_group_closed = FaceResult(has_faces=True, eyes_open=False, is_smiling=False,
                                 is_mid_blink=False, eyes_closed_aesthetic=False, face_count=3)
    # Eyes closed, 1 person — aesthetic
    fr_solo_closed = FaceResult(has_faces=True, eyes_open=False, is_smiling=False,
                                is_mid_blink=False, eyes_closed_aesthetic=True, face_count=1)
    # Mid-blink — should be worst
    fr_blink = FaceResult(has_faces=True, eyes_open=False, is_smiling=False,
                          is_mid_blink=True, eyes_closed_aesthetic=False, face_count=1)

    s_smile  = score_expression(fr_smile)
    s_group  = score_expression(fr_group_closed)
    s_solo   = score_expression(fr_solo_closed)
    s_blink  = score_expression(fr_blink)

    assert s_smile > s_solo,  f"smile ({s_smile}) > solo-closed ({s_solo})"
    assert s_solo  > s_group, f"solo-closed ({s_solo}) > group-closed ({s_group})"
    assert s_blink <= s_group, f"blink ({s_blink}) <= group-closed ({s_group})"


def test_dedup_removes_identical():
    from core.extractor import FrameCandidate
    from core import dedup
    frame = sharp_frame()
    candidates = [
        FrameCandidate(timestamp=float(i), frame_number=i, image=frame.copy(), score=1.0)
        for i in range(5)
    ]
    # All identical — only 1 should survive
    result = dedup.deduplicate(candidates)
    assert len(result) == 1, f"expected 1, got {len(result)}"


def test_dedup_keeps_different():
    from core.extractor import FrameCandidate
    from core import dedup
    candidates = [
        FrameCandidate(timestamp=float(i), frame_number=i,
                       image=np.random.randint(0, 255, (48, 64, 3), dtype=np.uint8),
                       score=1.0)
        for i in range(4)
    ]
    result = dedup.deduplicate(candidates)
    assert len(result) == len(candidates), \
        f"random frames should all survive, got {len(result)}/{len(candidates)}"


def test_exporter_creates_file():
    import tempfile
    from pathlib import Path
    from core.exporter import export_tiff
    frame = sharp_frame()
    with tempfile.TemporaryDirectory() as tmp:
        out = export_tiff(frame, Path(tmp), "test_video.mp4", 12.345)
        assert out.exists(), f"TIFF not created: {out}"
        assert out.suffix == ".tif"
        assert out.stat().st_size > 0
        assert "00m12s345ms" in out.name


def test_preset_crud():
    from config import presets
    name = "__smoke_test_preset__"
    data = {
        "output_mode": "exact", "exact_count": 42,
        "blur_mix_pct": 7, "auto_frames_per_sec": 12,
        "subfolder_per_video": False,
    }
    presets.save(name, data)
    loaded = presets.get(name)
    assert loaded is not None
    assert loaded["exact_count"] == 42
    presets.delete(name)
    assert presets.get(name) is None


def test_settings_roundtrip():
    from config import settings
    cfg = settings.load()
    assert "output_mode" in cfg
    assert "last_output_dir" in cfg
    assert "blur_mix_pct" in cfg


# ── Runner ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Frameable smoke tests\n")

    # core scoring
    print("Scoring:")
    test("sharpness: sharp > blurry",          test_sharpness)
    test("exposure: normal > dark/bright",     test_exposure)
    test("motion: still > moving",             test_motion)

    # face / expression
    print("\nFace analysis:")
    test("FaceResult defaults",                test_face_result_defaults)
    test("score_candidate (no face)",          test_score_no_face)
    test("expression hierarchy",               test_expression_scoring)

    # dedup
    print("\nDedup:")
    test("identical frames deduplicated",      test_dedup_removes_identical)
    test("different frames all kept",          test_dedup_keeps_different)

    # export
    print("\nExport:")
    test("TIFF created with correct name",     test_exporter_creates_file)

    # config / presets
    print("\nConfig:")
    test("preset save / load / delete",        test_preset_crud)
    test("settings load returns defaults",     test_settings_roundtrip)

    print(f"\n{PASS} passed  {FAIL} failed")
    sys.exit(0 if FAIL == 0 else 1)
