"""Primary converter: automate ytmp3vid.org / EasyConv via Playwright (MP3 320kbps)."""

from __future__ import annotations

import os
import re
import threading
import time
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

from .filenames import safe_filename, unique_path
from .paths import BROWSERS_DIR, apply_local_env

BASE_URL = "https://www.ytmp3vid.org/"
CONVERT_TIMEOUT_MS = 3_000
NAV_TIMEOUT_MS = 2_500

# ---------------------------------------------------------------------------
# Circuit breaker: auto-skip ytmp3vid after repeated failures
# ---------------------------------------------------------------------------
MAX_CONSECUTIVE_FAILURES = 1
_circuit_lock = threading.Lock()
_consecutive_failures = 0
_browser_semaphore = threading.Semaphore(1)  # Only 1 Playwright browser at a time


class Ytmp3Error(RuntimeError):
    """Raised when the website conversion path fails (caller should fall back)."""


def reset_circuit_breaker() -> None:
    """Reset the failure counter — call at the start of each batch."""
    global _consecutive_failures
    with _circuit_lock:
        _consecutive_failures = 0


def is_circuit_open() -> bool:
    """Return True if ytmp3vid has failed too many times and should be skipped."""
    with _circuit_lock:
        return _consecutive_failures >= MAX_CONSECUTIVE_FAILURES


def _record_failure() -> None:
    global _consecutive_failures
    with _circuit_lock:
        _consecutive_failures += 1


def _record_success() -> None:
    global _consecutive_failures
    with _circuit_lock:
        _consecutive_failures = 0


def download_mp3(url: str, music_dir: Path, preferred_name: str | None = None) -> Path:
    """
    Convert a YouTube URL to MP3 via ytmp3vid.org and save into music_dir.
    Prefers highest quality (320 kbps when offered).
    Skips instantly if the circuit breaker is open (too many recent failures).
    """
    # Circuit breaker: skip if ytmp3vid has failed too many times in a row
    if is_circuit_open():
        raise Ytmp3Error("Circuit breaker open — skipping ytmp3vid (too many consecutive failures)")

    # Chromium must live under project folder when C: is full
    apply_local_env()
    music_dir.mkdir(parents=True, exist_ok=True)
    headless = os.environ.get("HEADLESS", "1").strip() not in ("0", "false", "False", "no")
    if not any(BROWSERS_DIR.rglob("chrome.exe")):
        _record_failure()
        raise Ytmp3Error(
            f"Playwright Chromium not found in {BROWSERS_DIR}. "
            "Run setup.ps1 (installs browsers into this project folder)."
        )

    try:
        # Limit to 1 concurrent browser — prevents 10 browsers hammering the site
        if not _browser_semaphore.acquire(blocking=False):
            raise Ytmp3Error("ytmp3vid busy")
        try:
            return _run_playwright_session(url, music_dir, preferred_name, headless)
        finally:
            _browser_semaphore.release()
    except Ytmp3Error:
        _record_failure()
        raise
    except Exception as e:
        _record_failure()
        raise Ytmp3Error(str(e)) from e


def _run_playwright_session(url: str, music_dir: Path, preferred_name: str | None, headless: bool) -> Path:
    """Inner function: runs a single Playwright browser session (called under semaphore)."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        try:
            context = browser.new_context(
                accept_downloads=True,
                locale="en-US",
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
            )
            page = context.new_page()
            page.set_default_timeout(NAV_TIMEOUT_MS)

            target = f"{BASE_URL}?q={quote(url, safe='')}"
            try:
                page.goto(target, wait_until="domcontentloaded")
            except PlaywrightTimeout as e:
                raise Ytmp3Error(f"Navigation timeout: {e}") from e

            _dismiss_noise(page)
            _ensure_mp3_mode(page)
            _fill_url(page, url)
            _select_highest_quality(page)
            _click_convert(page)

            download_path = _wait_and_save_download(page, music_dir, preferred_name)
            context.close()
            _record_success()
            return download_path
        finally:
            browser.close()


def _dismiss_noise(page) -> None:
    """Best-effort close cookie banners / overlays."""
    for text in ("Accept", "I agree", "Got it", "OK", "Close", "×"):
        try:
            btn = page.get_by_role("button", name=re.compile(text, re.I))
            if btn.count() and btn.first.is_visible():
                btn.first.click(timeout=1500)
        except Exception:
            pass


def _ensure_mp3_mode(page) -> None:
    """Click MP3 tab/button if present."""
    candidates = [
        page.get_by_role("button", name=re.compile(r"^mp3$", re.I)),
        page.get_by_text(re.compile(r"^mp3$", re.I)),
        page.locator("button:has-text('MP3'), a:has-text('MP3'), [data-format='mp3']"),
        page.locator("label:has-text('MP3')"),
    ]
    for loc in candidates:
        try:
            if loc.count() and loc.first.is_visible():
                loc.first.click(timeout=2000)
                return
        except Exception:
            continue


def _fill_url(page, url: str) -> None:
    """Paste the YouTube URL into the main input."""
    selectors = [
        "input[type='url']",
        "input[type='text']",
        "input[placeholder*='URL' i]",
        "input[placeholder*='link' i]",
        "input[placeholder*='YouTube' i]",
        "textarea",
        "#url",
        "input.url",
        "input",
    ]
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() == 0:
                continue
            if not loc.is_visible():
                continue
            loc.click(timeout=2000)
            loc.fill("")
            loc.fill(url)
            return
        except Exception:
            continue
    # Fallback: type into focused field after click body
    raise Ytmp3Error("Could not find URL input on ytmp3vid.org")


def _select_highest_quality(page) -> None:
    """Pick 320kbps / highest audio quality if a control exists."""
    # Try select elements with bitrate options
    try:
        selects = page.locator("select")
        for i in range(selects.count()):
            sel = selects.nth(i)
            options = sel.locator("option")
            best_value = None
            best_score = -1
            for j in range(options.count()):
                opt = options.nth(j)
                text = (opt.inner_text() or "") + " " + (opt.get_attribute("value") or "")
                score = _quality_score(text)
                if score > best_score:
                    best_score = score
                    best_value = opt.get_attribute("value")
            if best_value is not None and best_score > 0:
                sel.select_option(best_value)
                return
    except Exception:
        pass

    # Click buttons/labels mentioning 320
    for pattern in (r"320\s*kbps", r"320", r"highest", r"best"):
        try:
            loc = page.get_by_text(re.compile(pattern, re.I))
            if loc.count() and loc.first.is_visible():
                loc.first.click(timeout=1500)
                return
        except Exception:
            continue


def _quality_score(text: str) -> int:
    t = text.casefold()
    if "320" in t:
        return 320
    if "256" in t:
        return 256
    if "192" in t:
        return 192
    if "128" in t:
        return 128
    if "64" in t:
        return 64
    if "high" in t or "best" in t:
        return 300
    return 0


def _click_convert(page) -> None:
    patterns = [
        re.compile(r"convert", re.I),
        re.compile(r"download", re.I),
        re.compile(r"start", re.I),
    ]
    for pat in patterns:
        try:
            btn = page.get_by_role("button", name=pat)
            if btn.count() and btn.first.is_visible():
                btn.first.click(timeout=3000)
                return
        except Exception:
            continue
        try:
            loc = page.locator(
                "button:has-text('Convert'), input[type='submit'], "
                "a:has-text('Convert'), button[type='submit']"
            )
            if loc.count() and loc.first.is_visible():
                loc.first.click(timeout=3000)
                return
        except Exception:
            continue
    raise Ytmp3Error("Could not find Convert button on ytmp3vid.org")


def _wait_and_save_download(page, music_dir: Path, preferred_name: str | None) -> Path:
    """Wait for download event or anchor href and save under Music/."""
    deadline = time.time() + CONVERT_TIMEOUT_MS / 1000.0
    last_err: Exception | None = None

    while time.time() < deadline:
        # Strategy 1: expect download event from a click
        try:
            with page.expect_download(timeout=5000) as di:
                # Try clicking any Download button that appeared
                dl_btn = page.get_by_role(
                    "link", name=re.compile(r"download", re.I)
                )
                if not dl_btn.count():
                    dl_btn = page.get_by_role(
                        "button", name=re.compile(r"download", re.I)
                    )
                if not dl_btn.count():
                    dl_btn = page.locator(
                        "a[download], a[href*='.mp3'], a:has-text('Download'), "
                        "button:has-text('Download')"
                    )
                if dl_btn.count() and dl_btn.first.is_visible():
                    dl_btn.first.click()
                else:
                    raise PlaywrightTimeout("no download control yet")
            download = di.value
            suggested = download.suggested_filename or "track.mp3"
            stem = preferred_name or Path(suggested).stem
            target = music_dir / f"{safe_filename(stem)}.mp3"
            download.save_as(str(target))
            if target.exists() and target.stat().st_size > 0:
                return target
        except PlaywrightTimeout as e:
            last_err = e
        except Exception as e:
            last_err = e

        # Strategy 2: direct href to mp3
        try:
            hrefs = page.locator("a[href*='.mp3'], a[href*='download']")
            for i in range(min(hrefs.count(), 5)):
                href = hrefs.nth(i).get_attribute("href")
                if not href or href.startswith("javascript"):
                    continue
                # Let playwright download via click
                with page.expect_download(timeout=8000) as di:
                    hrefs.nth(i).click()
                download = di.value
                suggested = download.suggested_filename or "track.mp3"
                stem = preferred_name or Path(suggested).stem
                target = music_dir / f"{safe_filename(stem)}.mp3"
                download.save_as(str(target))
                if target.exists() and target.stat().st_size > 0:
                    return target
        except Exception as e:
            last_err = e

        time.sleep(0.3)

    raise Ytmp3Error(
        f"Timed out waiting for MP3 download from ytmp3vid.org"
        + (f" ({last_err})" if last_err else "")
    )
