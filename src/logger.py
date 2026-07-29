"""
Music Agent - Logging & Error Tracking Module
---------------------------------------------
Provides central logging, unhandled exception catching,
system diagnostic information gathering, and log file utilities.
"""

from __future__ import annotations

import logging
import os
import platform
import shutil
import sys
import threading
import traceback
from pathlib import Path
from typing import Dict, List, Tuple

from src.paths import LOG_FILE, LOGS_DIR, ensure_local_dirs

_INITIALIZED = False


def setup_logging() -> logging.Logger:
    """
    Initialize logging handlers and register global exception hooks.
    Ensures log entries are written to logs/music_agent.log.
    """
    global _INITIALIZED
    ensure_local_dirs()

    logger = logging.getLogger("music_agent")

    if not _INITIALIZED:
        logger.setLevel(logging.DEBUG)

        # File handler
        try:
            file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
            file_handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter(
                "[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d]: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as exc:
            sys.stderr.write(f"Failed to setup file logging: {exc}\n")

        # Global exception hooks
        _install_exception_hooks(logger)
        _INITIALIZED = True

        logger.info("==================================================")
        logger.info("Music Agent Session Started")
        logger.info(f"OS: {platform.platform()} | Python: {platform.python_version()}")
        logger.info("==================================================")

    return logger


def get_logger(name: str = "music_agent") -> logging.Logger:
    """Retrieve logger instance."""
    setup_logging()
    return logging.getLogger(name)


def _install_exception_hooks(logger: logging.Logger) -> None:
    """Install global hooks to catch uncaught crashes in main thread or worker threads."""
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.critical(
            "Uncaught Exception in Main Thread!",
            exc_info=(exc_type, exc_value, exc_traceback),
        )

    def handle_thread_exception(args):
        logger.critical(
            f"Uncaught Exception in Thread '{args.thread.name}'!",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    sys.excepthook = handle_exception
    if hasattr(threading, "excepthook"):
        threading.excepthook = handle_thread_exception


def get_system_info() -> Dict[str, str]:
    """Gather diagnostic info about system environment to assist debugging on user PCs."""
    info = {
        "OS": f"{platform.system()} {platform.release()} ({platform.machine()})",
        "Python": sys.version.split()[0],
        "Standalone EXE": "Yes" if getattr(sys, "frozen", False) else "No (Script)",
        "FFmpeg": "Available ✅" if shutil.which("ffmpeg") else "Missing ❌",
    }

    try:
        import yt_dlp
        info["yt-dlp"] = getattr(yt_dlp.version, "__version__", "Installed")
    except Exception:
        info["yt-dlp"] = "Not Installed ❌"

    return info


def read_logs(max_bytes: int = 500000) -> str:
    """Read the contents of the log file, up to max_bytes from the end."""
    if not LOG_FILE.exists():
        return "No log records found yet."

    try:
        file_size = LOG_FILE.stat().st_size
        with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            if file_size > max_bytes:
                f.seek(file_size - max_bytes)
                # Skip partial line
                f.readline()
            return f.read()
    except Exception as exc:
        return f"Error reading log file: {exc}"


def get_error_counts() -> Tuple[int, int]:
    """Count number of ERROR and WARNING log lines in current log file."""
    if not LOG_FILE.exists():
        return (0, 0)

    errors = 0
    warnings = 0
    try:
        with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if " [ERROR] " in line or " [CRITICAL] " in line:
                    errors += 1
                elif " [WARNING] " in line:
                    warnings += 1
    except Exception:
        pass
    return (errors, warnings)


def clear_logs() -> bool:
    """Clear all log history."""
    try:
        if LOG_FILE.exists():
            with open(LOG_FILE, "w", encoding="utf-8") as f:
                f.truncate(0)
        logger = get_logger()
        logger.info("Log file cleared by user.")
        return True
    except Exception:
        return False
