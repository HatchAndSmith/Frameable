# PyInstaller spec — run: pyinstaller frameable.spec
import sys
import os
from pathlib import Path

block_cipher = None

# Bundle mediapipe's bundled models and data
try:
    import mediapipe as _mp
    _mp_root = Path(_mp.__file__).parent
    _mp_datas = []
    for _subdir in ("modules", "python/solutions"):
        _src = _mp_root / _subdir
        if _src.exists():
            _mp_datas.append((str(_src), f"mediapipe/{_subdir}"))
except ImportError:
    _mp_datas = []

a = Analysis(
    ["main.py"],
    pathex=[str(Path(".").resolve())],
    binaries=[],
    datas=[
        ("assets", "assets"),
        ("version.py", "."),
    ] + _mp_datas,
    hiddenimports=[
        # mediapipe
        "mediapipe",
        "mediapipe.python",
        "mediapipe.python.solutions",
        "mediapipe.python.solutions.face_mesh",
        "mediapipe.python.solutions.drawing_utils",
        # image / video
        "cv2",
        "tifffile",
        "imageio_ffmpeg",
        "PIL",
        "PIL.Image",
        "PIL.ImageDraw",
        "imagehash",
        # scene detection
        "scenedetect",
        "scenedetect.detectors",
        "scenedetect.video_manager",
        # cloud
        "google.cloud.vision",
        "google.cloud.vision_v1",
        "replicate",
        # system / keyring
        "keyring",
        "keyring.backends",
        "keyring.backends.macOS",
        "keyring.backends.Windows",
        "keyring.backends.SecretService",
        "keyring.backends.fail",
        # packaging / version check
        "packaging",
        "packaging.version",
        # app modules that PyInstaller might miss via dynamic imports
        "config.presets",
        "core.dedup",
        "core.log",
        "ui.presets_bar",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "scipy", "pandas", "notebook",
              "IPython", "jupyter"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Frameable",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon="assets/icon.ico" if sys.platform == "win32" else "assets/icon.icns",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Frameable",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Frameable.app",
        icon="assets/icon.icns",
        bundle_identifier="com.hatchandsmith.frameable",
        info_plist={
            "CFBundleShortVersionString": "1.0.0",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
            "NSRequiresAquaSystemAppearance": False,
        },
    )
