#!/usr/bin/env python3
"""
Music Download Agent
--------------------
Run via:  start.bat   or   python agent.py

Flow:
  1. On open: tell user to write "start" to begin
  2. Prompt for song names (batch list or one-by-one; Arabic OK)
  3. Silent gate: private token in the list/message or no download (never explained to users)
  4. Search YouTube for each name (exactly ONE video per name)
  5. Convert to MP3 via ytmp3vid.org (highest quality), fallback yt-dlp
  6. Save into ./Music — one MP3 file per song name
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.paths import MUSIC_DIR, apply_local_env

apply_local_env()

from src import ui
from src.arming import (
    REFUSAL_MESSAGE,
    extract_from_user_list,
    line_contains_arming,
    strip_arming_from_line,
)
from src.downloader import process_all, process_song


def main(argv: list[str] | None = None) -> int:
    ui.ensure_utf8()
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.kernel32.SetConsoleCP(65001)
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Music Download Agent")
    parser.add_argument(
        "songs",
        nargs="*",
        help="Song names to download",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Launch graphical user interface (GUI)",
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Force command-line interface interactive mode",
    )
    parser.add_argument(
        "--skip-ytmp3",
        action="store_true",
        help="Use yt-dlp only (skip website automation)",
    )
    parser.add_argument(
        "--one",
        action="store_true",
        help="One-by-one interactive mode",
    )
    parser.add_argument(
        "--parallel",
        "-p",
        action="store_true",
        help="Download songs concurrently in parallel (default behavior)",
    )
    parser.add_argument(
        "--sequential",
        "-s",
        action="store_true",
        help="Download songs one at a time (disables default parallelism)",
    )
    parser.add_argument(
        "--workers",
        "-w",
        type=int,
        default=0,
        help="Number of parallel worker threads (default: 50)",
    )
    args = parser.parse_args(argv)

    music_dir = MUSIC_DIR
    music_dir.mkdir(parents=True, exist_ok=True)

    # CLI with song args skips interactive UI
    if args.songs:
        skip = args.skip_ytmp3 or os.environ.get("SKIP_YTMP3", "").strip() in ("1", "true", "yes")
        workers = args.workers if args.workers > 0 else (1 if args.sequential else 50)
        return _run_batch(list(args.songs), music_dir, skip, max_workers=workers)

    # If --gui requested or default interactive startup without --cli, launch Desktop GUI
    if args.gui or not args.cli:
        try:
            from gui import MusicAgentApp
            app = MusicAgentApp()
            app.mainloop()
            return 0
        except Exception as err:
            print(f"[!] Unable to start GUI ({err}). Falling back to terminal mode...")

    skip = args.skip_ytmp3 or os.environ.get("SKIP_YTMP3", "").strip() in (
        "1",
        "true",
        "yes",
    )

    workers = args.workers
    if workers <= 0:
        if args.sequential:
            workers = 1
        else:
            # Default: 50 parallel workers (auto-parallel)
            workers = 50


    ui.print_banner(music_dir)

    # CLI with song args skips the interactive "start" gate
    if args.songs:
        return _run_batch(list(args.songs), music_dir, skip, max_workers=workers)

    if args.one:
        if not ui.wait_for_start():
            print("Bye.")
            return 0
        ui.print_song_prompt()
        return _one_by_one(music_dir, skip)

    # Interactive: must type "start" first
    if not ui.wait_for_start():
        print("Bye.")
        return 0

    ui.print_song_prompt()

    mode, names = ui.choose_mode()
    if mode == "exit":
        print("Bye.")
        return 0
    if mode == "one":
        return _one_by_one(music_dir, skip)

    if not names:
        print("No songs provided.")
        return 0

    return _run_batch(names, music_dir, skip, max_workers=workers)


def _run_batch(names: list[str], music_dir: Path, skip: bool, max_workers: int = 1) -> int:
    armed, songs = extract_from_user_list(names)
    if not armed:
        # Silent refusal — do not hint how to unlock
        print(REFUSAL_MESSAGE)
        return 2

    if not songs:
        print(REFUSAL_MESSAGE)
        return 0

    results, elapsed = process_all(names, music_dir, log=ui.log, skip_ytmp3=skip, max_workers=max_workers)
    if not results:
        print(REFUSAL_MESSAGE)
        return 0
    ui.summary(results, elapsed_seconds=elapsed)
    return 0 if all(r.get("ok") for r in results) else 1


def _one_by_one(music_dir: Path, skip: bool) -> int:
    """
    One-by-one: private token once in the session (silent if missing).
    Never print or hint the token to the user.
    """
    results: list[dict] = []
    session_armed = False
    print("One-by-one mode. Enter a song name after each download.")
    print("Type 'done' to finish.")
    print()

    while True:
        name = ui.read_one_by_one()
        if name is None:
            break

        if line_contains_arming(name):
            session_armed = True
            name = strip_arming_from_line(name)
            if not name:
                # Token-only line: unlock quietly, ask for next name
                continue

        if not session_armed:
            print(REFUSAL_MESSAGE)
            print()
            continue

        ui.log(f"[•] {name}")
        r = process_song(name, music_dir, log=ui.log, skip_ytmp3=skip)
        results.append(r)
        print()

    if results:
        ui.summary(results)
        return 0 if all(r.get("ok") for r in results) else 1
    print(REFUSAL_MESSAGE if not session_armed else "No songs downloaded.")
    return 2 if not session_armed else 0


if __name__ == "__main__":
    raise SystemExit(main())
