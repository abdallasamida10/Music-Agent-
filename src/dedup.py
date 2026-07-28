"""Rigid Deduplication Module for Music Agent.

Guarantees 1 song = 1 file:
1. Pre-download check: skips search & download if MP3 already exists in Music/.
2. Video ID check: skips download if YouTube video_id was already downloaded.
3. Disk cleanup: automatically removes duplicate files like '* (2).mp3', '* (3).mp3'.
"""

from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Any

from .filenames import safe_filename

REGISTRY_FILENAME = ".registry.json"
_LOCK = threading.Lock()


def _get_registry_path(music_dir: Path) -> Path:
    return music_dir / REGISTRY_FILENAME


def load_registry(music_dir: Path) -> dict[str, Any]:
    reg_path = _get_registry_path(music_dir)
    if not reg_path.exists():
        return {"queries": {}, "video_ids": {}}
    try:
        with open(reg_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {
                "queries": data.get("queries", {}),
                "video_ids": data.get("video_ids", {}),
            }
    except Exception:
        return {"queries": {}, "video_ids": {}}


def save_registry(music_dir: Path, data: dict[str, Any]) -> None:
    reg_path = _get_registry_path(music_dir)
    try:
        with open(reg_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def check_existing_song(query: str, music_dir: Path) -> Path | None:
    """
    Check if an MP3 file matching the user query already exists in music_dir.
    Returns the Path if found and valid (>0 bytes), otherwise None.
    """
    music_dir = music_dir.resolve()
    with _LOCK:
        # Check 1: direct filename match
        safe_name = safe_filename(query)
        candidate = music_dir / f"{safe_name}.mp3"
        if candidate.exists() and candidate.is_file() and candidate.stat().st_size > 0:
            return candidate

        # Check 2: registry lookup by normalized query
        registry = load_registry(music_dir)
        norm_query = query.strip().casefold()
        reg_info = registry["queries"].get(norm_query)
        if reg_info:
            stored_path = reg_info.get("path", "")
            # Check relative to music_dir first (machine-independent)
            local_cand = music_dir / Path(stored_path).name
            if local_cand.exists() and local_cand.is_file() and local_cand.stat().st_size > 0:
                return local_cand
            target_path = Path(stored_path)
            if target_path.exists() and target_path.is_file() and target_path.stat().st_size > 0:
                return target_path

        # Check 3: search for matching stem in music_dir
        if music_dir.exists():
            for item in music_dir.glob("*.mp3"):
                if item.name == ".gitkeep":
                    continue
                if safe_name.casefold() in item.stem.casefold() or item.stem.casefold() in safe_name.casefold():
                    if item.stat().st_size > 0:
                        return item

    return None


def check_existing_video_id(video_id: str, music_dir: Path) -> Path | None:
    """Check if a video_id has already been downloaded and exists in music_dir."""
    if not video_id:
        return None
    music_dir = music_dir.resolve()
    with _LOCK:
        registry = load_registry(music_dir)
        reg_info = registry["video_ids"].get(video_id)
        if reg_info:
            stored_path = reg_info.get("path", "")
            local_cand = music_dir / Path(stored_path).name
            if local_cand.exists() and local_cand.is_file() and local_cand.stat().st_size > 0:
                return local_cand
            target_path = Path(stored_path)
            if target_path.exists() and target_path.is_file() and target_path.stat().st_size > 0:
                return target_path
    return None


def register_download(query: str, video_id: str, title: str, file_path: Path, music_dir: Path) -> None:
    """Register a successful download into the registry."""
    music_dir = music_dir.resolve()
    with _LOCK:
        registry = load_registry(music_dir)
        norm_query = query.strip().casefold()
        info = {
            "query": query,
            "title": title,
            "video_id": video_id,
            "path": file_path.name,
            "abs_path": str(file_path.resolve()),
        }
        registry["queries"][norm_query] = info
        if video_id:
            registry["video_ids"][video_id] = info
        save_registry(music_dir, registry)


def purge_duplicate_files(music_dir: Path) -> None:
    """
    Purge duplicate files like 'Song (2).mp3', 'Song (3).mp3' from Music/.
    Keeps only the main 'Song.mp3' file.
    """
    if not music_dir.exists():
        return

    with _LOCK:
        dup_pattern = re.compile(r"^(.*?)\s*\(\d+\)\.mp3$", re.I)
        for item in list(music_dir.glob("*.mp3")):
            m = dup_pattern.match(item.name)
            if m:
                base_name = m.group(1).strip()
                main_file = music_dir / f"{base_name}.mp3"
                if main_file.exists() and main_file.stat().st_size > 0:
                    try:
                        item.unlink()
                    except Exception:
                        pass
                else:
                    # Rename the (2) file to main_file
                    try:
                        item.rename(main_file)
                    except Exception:
                        pass
