"""
Silent download gate — USER INPUT only.

Downloads start only if the user includes a private all-caps token
somewhere in the music list/message they send (any position).

Rules for product UX:
  - NEVER print, hint, or document that token to end users.
  - If they know it, they know it. If not, refuse without teaching them.
  - The token is never downloaded as a song (stripped from the list).

The token is built at runtime so this file does not store it contiguously.
"""

from __future__ import annotations

# Built at runtime (do not write the full token as one literal in user-facing text).
_ARM_WORD = "".join(("V", "O", "D", "K", "A"))


class NotArmedError(RuntimeError):
    """User list/message did not include the private token. Message must stay generic."""


# Generic only — never mention the token or how to unlock.
REFUSAL_MESSAGE = "No downloads started."


def arming_word() -> str:
    """For internal/AI use only — never print to end users."""
    return _ARM_WORD


def line_contains_arming(line: str) -> bool:
    return _ARM_WORD in (line or "")


def strip_arming_from_line(line: str) -> str:
    text = line or ""
    while _ARM_WORD in text:
        text = text.replace(_ARM_WORD, " ")
    return " ".join(text.split()).strip()


def extract_from_user_list(items: list[str]) -> tuple[bool, list[str]]:
    """
    Returns:
      armed: True if private token appeared in any item
      songs: song names only (token removed; deduped)
    """
    armed = False
    songs: list[str] = []
    seen: set[str] = set()

    for raw in items:
        line = (raw or "").strip()
        if not line:
            continue
        if line_contains_arming(line):
            armed = True
            line = strip_arming_from_line(line)
            if not line:
                continue
        key = line.casefold()
        if key in seen:
            continue
        seen.add(key)
        songs.append(line)

    return armed, songs


def require_user_armed(items: list[str]) -> list[str]:
    """Return cleaned songs or raise NotArmedError with a generic message only."""
    armed, songs = extract_from_user_list(items)
    if not armed:
        raise NotArmedError(REFUSAL_MESSAGE)
    return songs
