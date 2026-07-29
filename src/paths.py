"""Keep all caches, browsers, and downloads on the project drive (not C:)."""

from __future__ import annotations

import os
from pathlib import Path

import sys

# Project root: if compiled with PyInstaller, use executable directory; otherwise use parent of src/
if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).resolve().parent
else:
    ROOT = Path(__file__).resolve().parent.parent

MUSIC_DIR = (ROOT / "Music").resolve()
CACHE_DIR = (ROOT / ".cache").resolve()
BROWSERS_DIR = (ROOT / ".playwright-browsers").resolve()
LOGS_DIR = (ROOT / "logs").resolve()
LOG_FILE = (LOGS_DIR / "music_agent.log").resolve()
PIP_CACHE = (CACHE_DIR / "pip").resolve()
YTDLP_CACHE = (CACHE_DIR / "yt-dlp").resolve()
TEMP_DIR = (CACHE_DIR / "tmp").resolve()


def ensure_local_dirs() -> None:
    for d in (MUSIC_DIR, CACHE_DIR, BROWSERS_DIR, LOGS_DIR, PIP_CACHE, YTDLP_CACHE, TEMP_DIR):
        d.mkdir(parents=True, exist_ok=True)


def apply_local_env() -> None:
    """
    Force tools to write under the project folder on whatever drive the project lives (C:, E:, F:, etc.).
    Call this before importing/using playwright or yt-dlp when possible.
    """
    try:
        os.chdir(ROOT)
    except Exception:
        pass

    ensure_local_dirs()

    # Playwright Chromium (~180MB+) — keep in project folder
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(BROWSERS_DIR)

    # pip / temp scratch during installs
    os.environ.setdefault("PIP_CACHE_DIR", str(PIP_CACHE))
    os.environ["TEMP"] = str(TEMP_DIR)
    os.environ["TMP"] = str(TEMP_DIR)
    os.environ["TMPDIR"] = str(TEMP_DIR)

    # yt-dlp cache
    os.environ.setdefault("XDG_CACHE_HOME", str(CACHE_DIR))

    # Add local project root and bin directories to PATH so local ffmpeg binaries are found
    path_env = os.environ.get("PATH", "")
    bin_paths = [str(ROOT), str(ROOT / "bin"), str(CACHE_DIR / "ffmpeg")]
    new_paths = [p for p in bin_paths if p not in path_env]
    if new_paths:
        os.environ["PATH"] = os.pathsep.join(new_paths) + os.pathsep + path_env

