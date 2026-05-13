"""GitHub Releases-based auto-updater.

Checks https://api.github.com/repos/<OWNER>/<REPO>/releases/latest on launch.
If the published tag (vX.Y.Z) is newer than the running version, downloads
the IndexerSetup.exe asset and launches it silently. Inno Setup closes the
running app and reinstalls over the existing install.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from packaging.version import InvalidVersion, Version

from . import __version__

GITHUB_OWNER = "MHB2730"
GITHUB_REPO = "Indexer"
ASSET_NAME = "IndexerSetup.exe"
API_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
USER_AGENT = f"Indexer/{__version__}"
HTTP_TIMEOUT = 4.0


@dataclass
class UpdateInfo:
    latest_version: str
    current_version: str
    download_url: str
    asset_size: int          # bytes
    release_notes: str       # markdown body from the release


def _parse_version(tag: str) -> Version | None:
    tag = tag.lstrip("vV").strip()
    try:
        return Version(tag)
    except InvalidVersion:
        return None


def check_for_update() -> UpdateInfo | None:
    """Query GitHub Releases. Returns UpdateInfo if a newer version exists.

    Returns None on any error (no internet, no releases, parse failure, etc.)
    — auto-update must never block app launch.
    """
    try:
        req = urllib.request.Request(API_URL, headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
        })
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            data = json.load(resp)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None

    tag = data.get("tag_name", "")
    latest = _parse_version(tag)
    current = _parse_version(__version__)
    if latest is None or current is None or latest <= current:
        return None

    asset = next(
        (a for a in data.get("assets", []) if a.get("name") == ASSET_NAME),
        None,
    )
    if not asset:
        return None

    return UpdateInfo(
        latest_version=str(latest),
        current_version=str(current),
        download_url=asset["browser_download_url"],
        asset_size=int(asset.get("size", 0)),
        release_notes=data.get("body", "") or "",
    )


def _updates_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    p = base / "Indexer" / "Updates"
    p.mkdir(parents=True, exist_ok=True)
    return p


def download_installer(info: UpdateInfo,
                       progress: Callable[[int, int], None] | None = None) -> Path:
    """Stream the installer into the per-user updates folder.

    `progress(downloaded, total)` is called periodically if supplied.
    Returns the path to the downloaded file.
    """
    dest = _updates_dir() / f"IndexerSetup-v{info.latest_version}.exe"
    if dest.exists() and info.asset_size and dest.stat().st_size == info.asset_size:
        return dest  # already downloaded

    tmp = dest.with_suffix(".part")
    req = urllib.request.Request(info.download_url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp, open(tmp, "wb") as out:
        total = int(resp.headers.get("Content-Length") or info.asset_size or 0)
        downloaded = 0
        chunk_size = 1024 * 64
        while True:
            chunk = resp.read(chunk_size)
            if not chunk:
                break
            out.write(chunk)
            downloaded += len(chunk)
            if progress:
                progress(downloaded, total)
    tmp.replace(dest)
    return dest


def launch_installer_and_exit(installer: Path) -> None:
    """Spawn Inno Setup silently and quit so it can replace this exe.

    Flags:
      /VERYSILENT      — no UI
      /SUPPRESSMSGBOXES — no prompts
      /CLOSEAPPLICATIONS — close the running app cleanly
      /RESTARTAPPLICATIONS — relaunch after install
      /NORESTART       — do not reboot the machine
    """
    args = [
        str(installer),
        "/VERYSILENT", "/SUPPRESSMSGBOXES",
        "/CLOSEAPPLICATIONS", "/RESTARTAPPLICATIONS",
        "/NORESTART",
    ]
    # DETACHED_PROCESS so the installer outlives our exit.
    DETACHED_PROCESS = 0x00000008
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    creationflags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
    subprocess.Popen(
        args,
        close_fds=True,
        creationflags=creationflags,
    )
    sys.exit(0)
