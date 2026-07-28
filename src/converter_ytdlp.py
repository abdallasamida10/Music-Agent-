"""yt-dlp fallback: download best audio as MP3 into Music/.

Thread-safe: each download uses its own temp subdirectory to prevent
race conditions during parallel downloads.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any, Callable

import yt_dlp

from .filenames import safe_filename, unique_path
from .paths import TEMP_DIR, YTDLP_CACHE, ensure_local_dirs


def clean_non_mp3(music_dir: Path) -> None:
    """Purge any video or non-MP3 files from the Music folder."""
    if not music_dir.exists():
        return
    for item in music_dir.iterdir():
        if item.is_file():
            if item.name == ".gitkeep":
                continue
            if item.suffix.lower() != ".mp3":
                try:
                    item.unlink()
                except Exception:
                    pass


def _make_worker_temp() -> Path:
    """Create a unique temp directory for this download worker (thread-safe)."""
    worker_id = f"w{threading.current_thread().ident}_{int(time.time() * 1000)}"
    worker_dir = TEMP_DIR / worker_id
    worker_dir.mkdir(parents=True, exist_ok=True)
    return worker_dir


def _cleanup_worker_temp(worker_dir: Path) -> None:
    """Remove a worker's temp directory after download is done."""
    try:
        for f in worker_dir.iterdir():
            try:
                f.unlink()
            except Exception:
                pass
        worker_dir.rmdir()
    except Exception:
        pass


def download_mp3(
    url: str,
    music_dir: Path,
    preferred_name: str | None = None,
    progress_callback: Callable[[dict], None] | None = None,
) -> Path:
    """
    Download audio from YouTube URL as highest-quality MP3.
    Returns the path to the saved file.

    Thread-safe: uses an isolated temp directory per invocation.
    """
    ensure_local_dirs()
    music_dir.mkdir(parents=True, exist_ok=True)

    # Each worker gets its own temp dir to prevent parallel file collisions
    worker_temp = _make_worker_temp()

    try:
        outtmpl = str(worker_temp / "%(title)s.%(ext)s")

        ydl_opts: dict[str, Any] = {
            "format": "bestaudio/best",
            "outtmpl": outtmpl,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "keepvideo": False,
            "cachedir": str(YTDLP_CACHE),
            "retries": 3,
            "fragment_retries": 3,
            "concurrent_fragment_downloads": 4,
            "buffersize": 1024 * 1024,
            "extractor_args": {
                "youtube": {
                    "player_client": ["android", "ios", "mweb"],
                }
            },
            "http_headers": {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                )
            },
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "0",  # best / ~320kbps when available
                }
            ],
            # Prefer English metadata but keep original title for filename
            "restrictfilenames": False,
            "windowsfilenames": True,
        }

        if progress_callback:
            ydl_opts["progress_hooks"] = [progress_callback]

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                raise RuntimeError("yt-dlp returned no info")

            # Resolve final path after postprocessing
            title = info.get("title") or preferred_name or "track"

            # Look for the generated mp3 in this worker's temp dir
            written = _find_downloaded(worker_temp, music_dir, title, info)

            if preferred_name:
                target = music_dir / f"{safe_filename(preferred_name)}.mp3"
            else:
                target = music_dir / f"{safe_filename(title)}.mp3"

            if written and written.exists():
                if written.resolve() != target.resolve():
                    if target.exists():
                        try:
                            written.unlink()
                        except Exception:
                            pass
                        return target
                    written.replace(target)
                return target

            base = music_dir / f"{safe_filename(title)}.mp3"
            if base.exists():
                return base

            raise RuntimeError(f"MP3 not found after yt-dlp download for: {title}")
    finally:
        _cleanup_worker_temp(worker_temp)


def _find_downloaded(temp_dir: Path, music_dir: Path, title: str, info: dict) -> Path | None:
    """Locate the MP3 file yt-dlp wrote in temp_dir or music_dir."""
    for search_dir in (temp_dir, music_dir):
        for key in ("requested_downloads",):
            for item in info.get(key) or []:
                fp = item.get("filepath")
                if fp:
                    p = Path(fp)
                    mp3 = p.with_suffix(".mp3")
                    if mp3.exists():
                        return mp3
                    # Only return if it's an MP3 file
                    if p.exists() and p.suffix.lower() == ".mp3":
                        return p

        filename = info.get("_filename")
        if filename:
            p = Path(filename).with_suffix(".mp3")
            if p.exists():
                return p

        safe = safe_filename(title)
        candidate = search_dir / f"{safe}.mp3"
        if candidate.exists():
            return candidate

        mp3s = sorted(search_dir.glob("*.mp3"), key=lambda p: p.stat().st_mtime, reverse=True)
        fragment = safe[:20].casefold() if safe else ""
        for p in mp3s[:10]:
            if fragment and fragment in p.stem.casefold():
                return p
        if mp3s:
            return mp3s[0]

    return None

