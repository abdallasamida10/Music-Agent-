"""Resolve a song name to a YouTube video URL via yt-dlp search (no API key)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generator

import yt_dlp


@dataclass
class SearchResult:
    title: str
    url: str
    video_id: str


_SEARCH_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "skip_download": True,
    "noplaylist": True,  # never expand playlists
    "extract_flat": "in_playlist",
    "playlistend": 1,  # hard cap: one result only
    "default_search": "ytsearch1",
    "retries": 2,
    "extractor_args": {
        "youtube": {
            "player_client": ["android", "ios", "mweb"],
        }
    },
}


def _parse_result(info: dict | None, query: str) -> SearchResult:
    """Extract a SearchResult from yt-dlp info dict."""
    if not info:
        raise RuntimeError(f"No YouTube results for: {query}")

    # ytsearch returns a playlist-like dict with entries — take ONLY the first
    if "entries" in info:
        entries = [e for e in (info.get("entries") or []) if e]
        if not entries:
            raise RuntimeError(f"No YouTube results for: {query}")
        entry = entries[0]
    else:
        entry = info

    video_id = entry.get("id") or entry.get("url") or ""
    title = entry.get("title") or query
    url = entry.get("webpage_url") or entry.get("url")
    if not url and video_id:
        url = f"https://www.youtube.com/watch?v={video_id}"
    if not url:
        raise RuntimeError(f"Could not resolve URL for: {query}")

    # Normalize short / watch URLs
    if video_id and "youtube" not in url and "youtu.be" not in url:
        url = f"https://www.youtube.com/watch?v={video_id}"

    return SearchResult(title=title, url=url, video_id=video_id)


def search_youtube(query: str) -> SearchResult:
    """
    Search YouTube for `query` and return exactly ONE video (the top hit).
    Never returns playlists or multiple candidates.
    Supports Arabic and other Unicode query strings.
    """
    search_term = f"ytsearch1:{query}"
    with yt_dlp.YoutubeDL(_SEARCH_OPTS) as ydl:
        info = ydl.extract_info(search_term, download=False)
    return _parse_result(info, query)


def search_youtube_batch(
    queries: list[str],
) -> Generator[tuple[str, SearchResult | Exception], None, None]:
    """
    Search YouTube concurrently for each query (ultra-fast).
    Yields (query, SearchResult) tuples as each search completes.
    Still enforces ytsearch1 per query (1 result per name).
    """
    from concurrent.futures import ThreadPoolExecutor

    def _do_search(q: str) -> tuple[str, SearchResult | Exception]:
        try:
            res = search_youtube(q)
            return (q, res)
        except Exception as e:
            return (q, e)

    # Search up to 10 queries in parallel
    max_search_workers = min(len(queries), 10)
    with ThreadPoolExecutor(max_workers=max_search_workers) as executor:
        futures = [executor.submit(_do_search, q) for q in queries]
        for f in futures:
            yield f.result()
