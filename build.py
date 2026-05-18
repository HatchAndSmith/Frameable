"""
Build script — produces distributable zips for Mac and Windows.

Usage:
  python build.py

Outputs:
  dist/frameable-mac-v<version>.zip     (Mac)
  dist/frameable-windows-v<version>.zip (Windows)

Then create a GitHub Release tagged v<version> and attach the zips.
The app's auto-updater will find them automatically.
"""

import os
import platform
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from version import __version__


def run(cmd: list[str]):
    print(" ".join(cmd))
    subprocess.run(cmd, check=True)


def zip_dir(source: Path, dest: Path):
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in source.rglob("*"):
            zf.write(f, f.relative_to(source.parent))


def main():
    dist = Path("dist")
    dist.mkdir(exist_ok=True)

    run([sys.executable, "-m", "PyInstaller", "frameable.spec", "--clean", "--noconfirm"])

    plat = platform.system().lower()
    version = __version__

    if plat == "darwin":
        app = Path("dist/Frameable.app")
        if app.exists():
            out = dist / f"frameable-mac-v{version}.zip"
            zip_dir(app, out)
            print(f"\nBuilt: {out}")
        else:
            print("ERROR: Frameable.app not found in dist/")
            sys.exit(1)

    elif plat == "windows":
        folder = Path("dist/Frameable")
        if folder.exists():
            out = dist / f"frameable-windows-v{version}.zip"
            zip_dir(folder, out)
            print(f"\nBuilt: {out}")
        else:
            print("ERROR: dist/Frameable folder not found.")
            sys.exit(1)

    else:
        print(f"Unsupported platform: {plat}")
        sys.exit(1)

    print("\nNext steps:")
    print(f"  1. git tag v{version}")
    print(f"  2. git push origin v{version}")
    print(f"  3. Create GitHub Release at hatchandsmith/frameable")
    print(f"  4. Upload the zip as a release asset")
    print(f"  5. App users will see the update prompt on next launch")


if __name__ == "__main__":
    main()
