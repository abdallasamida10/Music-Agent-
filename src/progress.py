"""Professional Multi-Bar Progress Tracker for Parallel & Sequential Downloads.

Uses Rich progress display for live multi-task progress bars in terminal.
"""

from __future__ import annotations

import sys
import threading
import time
from typing import Any, Callable

try:
    from rich.console import Console
    from rich.progress import (
        BarColumn,
        DownloadColumn,
        Progress,
        SpinnerColumn,
        TaskID,
        TaskProgressColumn,
        TextColumn,
        TimeRemainingColumn,
        TransferSpeedColumn,
    )
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

_LOCK = threading.Lock()


class MultiSongProgress:
    """Manages multi-bar parallel progress display using Rich."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled and HAS_RICH and (sys.stdout is not None) and sys.stdout.isatty()
        self.progress: Progress | None = None
        self.tasks: dict[str, TaskID] = {}
        self._start_time: float | None = None
        self._timer_task: TaskID | None = None
        self._timer_thread: threading.Thread | None = None
        self._timer_stop = threading.Event()

        if self.enabled:
            console = Console(force_terminal=True, legacy_windows=False)
            self.progress = Progress(
                SpinnerColumn(),
                TextColumn("[bold cyan]{task.description}[/bold cyan]"),
                BarColumn(bar_width=30, style="black on blue", complete_style="green"),
                TaskProgressColumn(),
                DownloadColumn(),
                TransferSpeedColumn(),
                TimeRemainingColumn(),
                console=console,
                refresh_per_second=10,
                transient=False,
            )

    def start(self) -> None:
        if self.enabled and self.progress:
            self._start_time = time.time()
            # Add a timer row at the top of the progress display
            self._timer_task = self.progress.add_task(
                "[bold magenta]⏱ Elapsed: 00:00[/bold magenta]",
                total=None,  # indeterminate — no bar, just spinner + text
            )
            self.progress.start()
            # Background thread to update the elapsed timer every second
            self._timer_stop.clear()
            self._timer_thread = threading.Thread(target=self._tick_timer, daemon=True)
            self._timer_thread.start()

    def _tick_timer(self) -> None:
        """Update the elapsed time header every second."""
        while not self._timer_stop.is_set():
            if self.progress and self._timer_task is not None and self._start_time:
                elapsed = time.time() - self._start_time
                mins, secs = divmod(int(elapsed), 60)
                hrs, mins = divmod(mins, 60)
                if hrs > 0:
                    time_str = f"{hrs:02d}:{mins:02d}:{secs:02d}"
                else:
                    time_str = f"{mins:02d}:{secs:02d}"
                try:
                    self.progress.update(
                        self._timer_task,
                        description=f"[bold magenta]⏱ Elapsed: {time_str}[/bold magenta]",
                    )
                except Exception:
                    pass
            self._timer_stop.wait(1.0)

    def stop(self) -> None:
        self._timer_stop.set()
        if self._timer_thread:
            self._timer_thread.join(timeout=2)
        if self.enabled and self.progress:
            # Final elapsed time update
            if self._timer_task is not None and self._start_time:
                elapsed = time.time() - self._start_time
                mins, secs = divmod(int(elapsed), 60)
                hrs, mins = divmod(mins, 60)
                if hrs > 0:
                    time_str = f"{hrs:02d}:{mins:02d}:{secs:02d}"
                else:
                    time_str = f"{mins:02d}:{secs:02d}"
                try:
                    self.progress.update(
                        self._timer_task,
                        description=f"[bold green]⏱ Total time: {time_str}[/bold green]",
                    )
                except Exception:
                    pass
            try:
                self.progress.stop()
            except Exception:
                pass

    def get_elapsed(self) -> float:
        """Return elapsed seconds since start, or 0 if not started."""
        if self._start_time is None:
            return 0.0
        return time.time() - self._start_time

    def add_song(self, song_name: str) -> TaskID | None:
        if not self.enabled or not self.progress:
            return None
        with _LOCK:
            desc = song_name[:35] + ("..." if len(song_name) > 35 else "")
            task_id = self.progress.add_task(f"[yellow]{desc}[/yellow]", total=100)
            self.tasks[song_name] = task_id
            return task_id

    def update_status(self, song_name: str, status_msg: str) -> None:
        if not self.enabled or not self.progress:
            return
        with _LOCK:
            task_id = self.tasks.get(song_name)
            if task_id is not None:
                desc = f"{song_name[:25]}... ({status_msg})" if len(song_name) > 25 else f"{song_name} ({status_msg})"
                self.progress.update(task_id, description=f"[cyan]{desc}[/cyan]")

    def update_yt_dlp(self, song_name: str, data: dict[str, Any]) -> None:
        if not self.enabled or not self.progress:
            return
        task_id = self.tasks.get(song_name)
        if task_id is None:
            return

        status = data.get("status")
        if status == "downloading":
            total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
            downloaded = data.get("downloaded_bytes") or 0
            with _LOCK:
                desc = song_name[:30] + ("..." if len(song_name) > 30 else "")
                if total > 0:
                    self.progress.update(
                        task_id,
                        description=f"[green]Downloading: {desc}[/green]",
                        completed=downloaded,
                        total=total,
                    )
                else:
                    self.progress.update(
                        task_id,
                        description=f"[green]Downloading: {desc}[/green]",
                        completed=downloaded,
                    )
        elif status == "finished":
            with _LOCK:
                desc = song_name[:30] + ("..." if len(song_name) > 30 else "")
                self.progress.update(
                    task_id,
                    description=f"[bold green]✓ {desc}[/bold green]",
                    completed=100,
                    total=100,
                )

    def mark_completed(self, song_name: str, method: str = "OK") -> None:
        if not self.enabled or not self.progress:
            return
        with _LOCK:
            task_id = self.tasks.get(song_name)
            if task_id is not None:
                desc = song_name[:35] + ("..." if len(song_name) > 35 else "")
                self.progress.update(
                    task_id,
                    description=f"[bold green]✓ {desc} ({method})[/bold green]",
                    completed=100,
                    total=100,
                )

    def mark_failed(self, song_name: str, error: str = "FAILED") -> None:
        if not self.enabled or not self.progress:
            return
        with _LOCK:
            task_id = self.tasks.get(song_name)
            if task_id is not None:
                desc = song_name[:30] + ("..." if len(song_name) > 30 else "")
                self.progress.update(
                    task_id,
                    description=f"[bold red]✗ {desc} (Failed)[/bold red]",
                )
