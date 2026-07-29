"""Orchestrate: search → ytmp3vid primary → yt-dlp fallback.

Rule: 1 song name → exactly 1 YouTube video → exactly 1 MP3 file.
Downloads only run when the user included the arming word in their list.
"""

from __future__ import annotations

import queue
import time
from pathlib import Path
from typing import Callable

from . import converter_ytdlp, converter_ytmp3
from .arming import NotArmedError, require_user_armed
from .converter_ytdlp import clean_non_mp3
from .converter_ytmp3 import Ytmp3Error, is_circuit_open, reset_circuit_breaker
from .dedup import (
    check_existing_song,
    check_existing_video_id,
    purge_duplicate_files,
    register_download,
)
from .filenames import safe_filename
from .logger import get_logger
from .progress import MultiSongProgress
from .youtube_search import SearchResult, search_youtube, search_youtube_batch

LogFn = Callable[[str], None]
logger = get_logger("downloader")


def process_song(
    query: str,
    music_dir: Path,
    log: LogFn | None = None,
    *,
    skip_ytmp3: bool = False,
    seen_video_ids: set[str] | None = None,
    progress: MultiSongProgress | None = None,
    search_result: SearchResult | None = None,
) -> dict:
    """
    Download exactly ONE song for this query.
    Rigid Algorithm: Skips download if file or video_id already exists in Music/.
    If search_result is provided, skips the YouTube search step (pre-searched).
    """
    def _log(msg: str) -> None:
        if log:
            log(msg)

    result: dict = {
        "query": query,
        "ok": False,
        "method": None,
        "path": None,
        "title": None,
        "url": None,
        "video_id": None,
        "error": None,
    }

    # Step 1: Rigid Pre-Download Existing Song Check
    existing_file = check_existing_song(query, music_dir)
    if existing_file:
        result["ok"] = True
        result["method"] = "skipped_existing"
        result["path"] = str(existing_file)
        if progress:
            progress.mark_completed(query, "existing")
        _log(f"  → Song already exists on disk — skipping: {existing_file.name}")
        return result

    # Step 1b: Use pre-searched result or search now
    if search_result is not None:
        found = search_result
        # Already logged by _search_feeder — don't duplicate
    else:
        if progress:
            progress.update_status(query, "Searching YouTube...")
        try:
            _log(f"  → Searching YouTube (1 result only): {query}")
            found = search_youtube(query)
            _log(f"  → One match: {found.title}")
            _log(f"  → URL: {found.url}")
        except Exception as e:
            result["error"] = f"YouTube search failed: {e}"
            logger.error(f"YouTube search failed for query '{query}': {e}", exc_info=True)
            if progress:
                progress.mark_failed(query, "search_failed")
            _log(f"  → FAIL search: {e}")
            return result

    result["title"] = found.title
    result["url"] = found.url
    result["video_id"] = found.video_id

    # Step 2: Rigid Video ID Existing Check
    if found.video_id:
        if seen_video_ids is not None and found.video_id in seen_video_ids:
            result["ok"] = True
            result["method"] = "skipped_duplicate"
            if progress:
                progress.mark_completed(query, "duplicate")
            _log("  → Same video already downloaded in this batch — skipping")
            return result

        vid_file = check_existing_video_id(found.video_id, music_dir)
        if vid_file:
            result["ok"] = True
            result["method"] = "skipped_duplicate"
            result["path"] = str(vid_file)
            if progress:
                progress.mark_completed(query, "duplicate")
            _log(f"  → Same YouTube video already saved ({vid_file.name}) — skipping")
            return result

    preferred = safe_filename(query)

    def _ytdlp_progress_cb(data: dict) -> None:
        if progress:
            progress.update_yt_dlp(query, data)
        if data.get("status") == "downloading":
            total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
            downloaded = data.get("downloaded_bytes") or 0
            if total > 0:
                pct = int((downloaded / total) * 100)
                _log(f"⚡ {query} ({pct}%)")
            else:
                _log(f"⚡ {query} (downloading...)")
        elif data.get("status") == "finished":
            _log(f"⚡ {query} (converting to MP3...)")


    # Try ytmp3vid unless skipped or circuit breaker is open
    if not skip_ytmp3 and not is_circuit_open():
        try:
            if progress:
                progress.update_status(query, "ytmp3vid...")
            path = converter_ytmp3.download_mp3(
                found.url, music_dir, preferred_name=preferred
            )
            result["ok"] = True
            result["method"] = "ytmp3vid"
            result["path"] = str(path)
            if seen_video_ids is not None and found.video_id:
                seen_video_ids.add(found.video_id)
            register_download(query, found.video_id, found.title, path, music_dir)
            if progress:
                progress.mark_completed(query, "ytmp3vid")
            _log(f"  → OK (ytmp3vid) → {path.name}")
            return result
        except (Ytmp3Error, Exception):
            pass

    try:
        if progress:
            progress.update_status(query, "Downloading...")
        path = converter_ytdlp.download_mp3(
            found.url,
            music_dir,
            preferred_name=preferred,
            progress_callback=_ytdlp_progress_cb,
        )
        result["ok"] = True
        result["method"] = "yt-dlp"
        result["path"] = str(path)
        if seen_video_ids is not None and found.video_id:
            seen_video_ids.add(found.video_id)
        register_download(query, found.video_id, found.title, path, music_dir)
        if progress:
            progress.mark_completed(query, "yt-dlp")
        _log(f"  → OK (yt-dlp) → {path.name}")
        return result
    except Exception as e:
        result["error"] = f"yt-dlp failed: {e}"
        logger.error(f"Download failed for query '{query}' ({found.url}): {e}", exc_info=True)
        if progress:
            progress.mark_failed(query, str(e))
        _log(f"  → FAIL yt-dlp: {e}")
        return result


def process_all(
    queries: list[str],
    music_dir: Path,
    log: LogFn | None = None,
    *,
    delay_sec: float = 2.0,
    skip_ytmp3: bool = False,
    max_workers: int = 50,
) -> tuple[list[dict], float]:
    """
    Process user list: require arming word in the list, then one MP3 per song.
    The arming word itself is never treated as a song name.

    Pipeline architecture:
      1. Search phase: batch-search all songs with a single yt-dlp instance
         (sequential — yt-dlp search is not thread-safe).
      2. Download phase: feed search results into a pool of download workers
         that run concurrently (default 3 workers).
    """
    import os
    import random
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import threading

    try:
        songs = require_user_armed(queries)
    except NotArmedError as e:
        # Generic refusal only — never explain the private gate
        if log:
            log(str(e))
        return [
            {
                "query": "(list)",
                "ok": False,
                "method": None,
                "path": None,
                "title": None,
                "url": None,
                "video_id": None,
                "error": str(e),
            }
        ], 0.0

    if not songs:
        return [], 0.0

    purge_duplicate_files(music_dir)

    # Reset circuit breaker for each new batch
    reset_circuit_breaker()

    if max_workers <= 1:
        parallel_env = os.environ.get("PARALLEL", "").strip() or os.environ.get("MAX_WORKERS", "").strip()
        if parallel_env:
            try:
                max_workers = int(parallel_env)
            except ValueError:
                if parallel_env.lower() in ("1", "true", "yes"):
                    max_workers = 3

    seen_video_ids: set[str] = set()
    lock = threading.Lock()

    def thread_safe_log(msg: str) -> None:
        if log:
            with lock:
                log(msg)

    total = len(songs)

    # Cap workers: one per song, max 50 — each song gets its own "subagent"
    if max_workers > 1:
        max_workers = min(max_workers, total, 50)

    progress_mgr = MultiSongProgress(enabled=True)
    for s in songs:
        progress_mgr.add_song(s)

    progress_mgr.start()

    try:
        # ---------------------------------------------------------------
        # Pipeline: search phase feeds into download phase
        # ---------------------------------------------------------------
        if max_workers > 1:
            thread_safe_log(f"[*] Pipeline mode: {max_workers} parallel workers (searching + downloading)...")

            # Search results queue: search thread produces, download workers consume
            search_q: queue.Queue[tuple[int, str, SearchResult | Exception | None]] = queue.Queue()

            def _search_feeder() -> None:
                """Run batch search in a background thread, feed results into queue."""
                idx = 1
                for query, result in search_youtube_batch(songs):
                    thread_safe_log(f"[{idx}/{total}] {query}")
                    thread_safe_log(f"  → Searching YouTube (1 result only): {query}")
                    if isinstance(result, Exception):
                        thread_safe_log(f"  → FAIL search: {result}")
                    else:
                        thread_safe_log(f"  → One match: {result.title}")
                        thread_safe_log(f"  → URL: {result.url}")
                    search_q.put((idx, query, result))
                    idx += 1
                # Sentinel: signals all searches are done
                search_q.put((-1, "", None))

            # Start search feeder in background
            search_thread = threading.Thread(target=_search_feeder, daemon=True)
            search_thread.start()

            # Download workers consume from the queue
            results_map: dict[int, dict] = {}

            def _download_worker(idx: int, query: str, found: SearchResult) -> tuple[int, dict]:
                # No stagger: fire immediately like an independent subagent
                def _log(msg: str) -> None:
                    thread_safe_log(msg)

                r = process_song(
                    query,
                    music_dir,
                    log=_log,
                    skip_ytmp3=skip_ytmp3,
                    seen_video_ids=seen_video_ids,
                    progress=progress_mgr,
                    search_result=found,
                )
                return (idx, r)

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = []
                while True:
                    item = search_q.get()
                    idx, query, search_result = item
                    if idx == -1:
                        break  # All searches done

                    if isinstance(search_result, Exception):
                        # Search failed — record immediately, no download
                        results_map[idx] = {
                            "query": query,
                            "ok": False,
                            "method": None,
                            "path": None,
                            "title": None,
                            "url": None,
                            "video_id": None,
                            "error": f"YouTube search failed: {search_result}",
                        }
                        if progress_mgr:
                            progress_mgr.mark_failed(query, "search_failed")
                        continue

                    # Submit download to thread pool
                    futures.append(executor.submit(_download_worker, idx, query, search_result))

                # Collect download results
                for future in as_completed(futures):
                    try:
                        idx, r = future.result()
                        results_map[idx] = r
                    except Exception as ex:
                        # Should not happen, but safety net
                        results_map[idx] = {
                            "query": "unknown",
                            "ok": False,
                            "error": str(ex),
                        }

            search_thread.join(timeout=5)
            clean_non_mp3(music_dir)
            purge_duplicate_files(music_dir)
            elapsed = progress_mgr.get_elapsed()
            return [results_map[i] for i in sorted(results_map.keys())], elapsed

        # ---------------------------------------------------------------
        # Sequential mode (max_workers=1): still use batch search for speed
        # ---------------------------------------------------------------
        results: list[dict] = []
        search_cache: dict[str, SearchResult] = {}

        # Pre-search all songs with single yt-dlp instance
        thread_safe_log("[*] Batch-searching all songs...")
        for query, search_result in search_youtube_batch(songs):
            if isinstance(search_result, Exception):
                thread_safe_log(f"  → Search failed for '{query}': {search_result}")
            else:
                search_cache[query] = search_result
                thread_safe_log(f"  → Found: {search_result.title}")

        for i, q in enumerate(songs, start=1):
            if log:
                log(f"[{i}/{total}] {q}")
            cached = search_cache.get(q)
            results.append(
                process_song(
                    q,
                    music_dir,
                    log=log,
                    skip_ytmp3=skip_ytmp3,
                    seen_video_ids=seen_video_ids,
                    progress=progress_mgr,
                    search_result=cached,
                )
            )
            # Minimal delay between sequential downloads (no more 1.8-3.5s waits)
            if i < total:
                time.sleep(random.uniform(0.3, 0.8))

        clean_non_mp3(music_dir)
        purge_duplicate_files(music_dir)
        elapsed = progress_mgr.get_elapsed()
        return results, elapsed
    finally:
        progress_mgr.stop()

