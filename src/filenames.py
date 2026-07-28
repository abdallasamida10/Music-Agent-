"""Safe Windows filenames (keeps Arabic and other Unicode letters)."""

from __future__ import annotations

import re
from pathlib import Path

# Windows-reserved characters and control chars
_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def safe_filename(name: str, max_len: int = 120) -> str:
    """Sanitize for Windows paths while preserving Arabic/Unicode letters."""
    name = (name or "track").strip()
    name = _ILLEGAL.sub("", name)
    name = name.rstrip(" .")
    if not name:
        name = "track"
    # Reserved device names
    stem = name.split(".")[0].upper()
    if stem in _RESERVED:
        name = f"_{name}"
    if len(name) > max_len:
        name = name[:max_len].rstrip(" .")
    return name


def unique_path(path: Path) -> Path:
    """Return the exact path. Rigid algorithm prevents creating duplicate (2), (3) files."""
    return path
