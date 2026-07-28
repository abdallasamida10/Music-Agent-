"""Terminal UI: banners, song input (batch / one-by-one), progress logs."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def ensure_utf8() -> None:
    """Best-effort UTF-8 console setup for Arabic and other scripts on Windows."""
    if sys.stdout is None or sys.stderr is None:
        if sys.platform == "win32":
            try:
                import ctypes
                if ctypes.windll.kernel32.AttachConsole(-1):
                    if sys.stdout is None:
                        sys.stdout = open("CONOUT$", "w", encoding="utf-8", buffering=1)
                    if sys.stderr is None:
                        sys.stderr = open("CONOUT$", "w", encoding="utf-8", buffering=1)
            except Exception:
                pass
        if sys.stdout is None:
            sys.stdout = open(os.devnull, "w", encoding="utf-8")
        if sys.stderr is None:
            sys.stderr = open(os.devnull, "w", encoding="utf-8")

    for stream in (sys.stdout, sys.stderr, sys.stdin):
        if stream is not None:
            try:
                stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
            except Exception:
                pass


def print_banner(music_dir: Path) -> None:
    print()
    print("=" * 48)
    print("  Music Download Agent")
    print(f"  Output folder: {music_dir}")
    print("=" * 48)
    print()
    print("Write start to begin")
    print("  (or type 'exit' to quit)")
    print()


def wait_for_start() -> bool:
    """
    Wait until the user types 'start'.
    Returns True when started, False if they exit.
    """
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return False

        lower = line.casefold()
        if lower in ("exit", "quit", "q"):
            return False
        if lower == "start":
            return True
        if not line:
            print("Write start to begin")
            continue
        print("Write start to begin")


def print_song_prompt() -> None:
    print()
    print("Send all the music names")
    print("  • Paste one song per line, then empty line or 'done'")
    print("  • Or type 'one' for one-by-one mode")
    print("  • Rule: 1 song name = 1 video = 1 MP3")
    print("  • Arabic names supported | 'exit' to quit")
    print()


def read_batch_names() -> list[str] | None:
    """
    Read a batch of song names.
    Returns None if user wants to exit.
    First line 'one' switches to one-by-one mode (returns empty list with sentinel via special).
    """
    names: list[str] = []

    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return None

        lower = line.casefold()
        if lower in ("exit", "quit", "q"):
            return None
        if lower == "one":
            return []  # empty list signals one-by-one when combined with mode flag
        if lower in ("done", "") and names:
            break
        if lower in ("done", ""):
            # empty list and done with no names
            if not names:
                print("No names yet. Enter a song name, 'one', or 'exit'.")
                continue
            break
        if line:
            names.append(line)

    return _dedupe(names)


def read_one_by_one() -> str | None:
    """Prompt for a single song name. Returns None to stop."""
    try:
        line = input("Song name (or 'done'/'exit'): ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None

    lower = line.casefold()
    if lower in ("done", "exit", "quit", "q", ""):
        return None
    return line


def choose_mode() -> tuple[str, list[str]]:
    """
    Returns (mode, names).
    mode is 'batch' | 'one' | 'exit'.
    For batch, names is the full list. For one, names is empty (caller loops).
    """
    names = read_batch_names()
    if names is None:
        return "exit", []
    if names == []:
        # User typed 'one' as first command
        print()
        print("One-by-one mode. Enter a song after each download.")
        print()
        return "one", []
    return "batch", names


def log(msg: str) -> None:
    print(msg)


def log_step(msg: str, indent: int = 1) -> None:
    print("  " * indent + msg)


def summary(results: list[dict], elapsed_seconds: float = 0.0) -> None:
    ok = sum(1 for r in results if r.get("ok"))
    failed = len(results) - ok
    print()
    print("-" * 48)
    if elapsed_seconds > 0:
        mins, secs = divmod(int(elapsed_seconds), 60)
        hrs, mins = divmod(mins, 60)
        if hrs > 0:
            time_str = f"{hrs:02d}:{mins:02d}:{secs:02d}"
        else:
            time_str = f"{mins:02d}:{secs:02d}"
        print(f"⏱  Total time: {time_str}")
    print(f"Done: {ok} ok, {failed} failed")
    for r in results:
        status = "OK" if r.get("ok") else "FAIL"
        method = r.get("method") or "-"
        path = r.get("path") or r.get("error") or ""
        print(f"  [{status}] {r.get('query')}  ({method})  {path}")
    print("-" * 48)
    print()


def _dedupe(names: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for n in names:
        key = n.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(n)
    return out
