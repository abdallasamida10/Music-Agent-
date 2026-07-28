"""Keep all caches, browsers, and downloads on the project drive (not C:)."""

from __future__ import annotations

import os
from pathlib import Path

# Project root = parent of src/
ROOT = Path(__file__).resolve().parent.parent
MUSIC_DIR = ROOT / "Music"
CACHE_DIR = ROOT / ".cache"
BROWSERS_DIR = ROOT / ".playwright-browsers"
PIP_CACHE = CACHE_DIR / "pip"
YTDLP_CACHE = CACHE_DIR / "yt-dlp"
TEMP_DIR = CACHE_DIR / "tmp"


def ensure_local_dirs() -> None:
    for d in (MUSIC_DIR, CACHE_DIR, BROWSERS_DIR, PIP_CACHE, YTDLP_CACHE, TEMP_DIR):
        d.mkdir(parents=True, exist_ok=True)


def apply_local_env() -> None:
    """
    Force tools to write under the project folder on E: (or wherever the project lives).
    Call this before importing/using playwright or yt-dlp when possible.
    """
    ensure_local_dirs()

    # Playwright Chromium (~180MB+) — never default to %USERPROFILE% on C:
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(BROWSERS_DIR)

    # pip / temp scratch during installs
    os.environ.setdefault("PIP_CACHE_DIR", str(PIP_CACHE))
    os.environ["TEMP"] = str(TEMP_DIR)
    os.environ["TMP"] = str(TEMP_DIR)
    os.environ["TMPDIR"] = str(TEMP_DIR)

    # yt-dlp cache
    os.environ.setdefault("XDG_CACHE_HOME", str(CACHE_DIR))
