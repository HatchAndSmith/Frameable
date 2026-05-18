import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import requests
from packaging.version import Version

GITHUB_REPO = "hatchandsmith/frameable"
GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
_HEADERS = {"Accept": "application/vnd.github.v3+json", "User-Agent": "Frameable"}


def check_for_update(current_version: str) -> tuple[str | None, str | None]:
    try:
        resp = requests.get(GITHUB_API, headers=_HEADERS, timeout=6)
        if resp.status_code != 200:
            return None, None
        data = resp.json()
        tag = data.get("tag_name", "").lstrip("v")
        if not tag:
            return None, None
        if Version(tag) > Version(current_version):
            platform = "windows" if sys.platform == "win32" else "mac"
            for asset in data.get("assets", []):
                if platform in asset["name"].lower():
                    return tag, asset["browser_download_url"]
            return tag, None
        return None, None
    except Exception:
        return None, None


def download_and_install(download_url: str, progress_callback=None):
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        zip_path = tmp_path / "update.zip"

        resp = requests.get(download_url, stream=True, timeout=120, headers=_HEADERS)
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        downloaded = 0

        with open(zip_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                f.write(chunk)
                downloaded += len(chunk)
                if progress_callback and total > 0:
                    progress_callback(int(downloaded / total * 100))

        if sys.platform == "win32":
            _install_windows(zip_path, tmp_path)
        else:
            _install_mac(zip_path, tmp_path)


def _install_windows(zip_path: Path, tmp_path: Path):
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(tmp_path)
    installers = list(tmp_path.glob("*.exe"))
    if installers:
        subprocess.Popen([str(installers[0]), "/SILENT", "/NORESTART"])
    os._exit(0)


def _install_mac(zip_path: Path, tmp_path: Path):
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(tmp_path)
    apps = list(tmp_path.glob("*.app"))
    if not apps:
        raise RuntimeError("Update package missing .app bundle.")
    new_app = apps[0]

    exe = Path(sys.executable)
    app_path = exe
    while app_path.suffix != ".app" and app_path != app_path.parent:
        app_path = app_path.parent

    if app_path.suffix != ".app":
        raise RuntimeError("Cannot locate current .app bundle.")

    script = f"""#!/bin/bash
sleep 1
rm -rf "{app_path}"
cp -r "{new_app}" "{app_path}"
open "{app_path}"
"""
    sh = tmp_path / "install.sh"
    sh.write_text(script)
    sh.chmod(0o755)
    subprocess.Popen(["bash", str(sh)])
    os._exit(0)
