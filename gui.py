#!/usr/bin/env python3
"""
Music Agent - Graphical User Interface (GUI)
--------------------------------------------
A modern, dark-themed GUI built with CustomTkinter for downloading high-quality MP3s.
Automatically operates at maximum speed (fast yt-dlp mode + parallel multi-worker downloads).
"""

from __future__ import annotations

import os
import shutil
import sys
import threading
import time
import traceback
from pathlib import Path
import tkinter as tk
from typing import Dict, List, Optional

# Safety: pythonw.exe sets sys.stdout/stderr to None which crashes
# any print(), logging, or Rich usage in background threads.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

# Ensure project root is on sys.path
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.paths import MUSIC_DIR, LOGS_DIR, apply_local_env
apply_local_env()

import customtkinter as ctk

from src.downloader import process_all
from src.arming import extract_from_user_list, REFUSAL_MESSAGE
from src.logger import (
    setup_logging,
    get_logger,
    get_system_info,
    read_logs,
    get_error_counts,
    clear_logs,
)

# Set CustomTkinter theme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class MusicAgentApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        # Initialize logging
        self.logger = setup_logging()
        self.logger.info("Initializing MusicAgentApp GUI window.")

        self.title("Music Agent")

        self.geometry("820x650")
        self.minsize(750, 550)

        # State variables
        self.is_downloading = False
        self.download_thread: Optional[threading.Thread] = None
        self.song_widgets: Dict[str, Dict[str, ctk.CTkLabel]] = {}
        self.start_time: float = 0.0
        self.logs_window: Optional[LogsDialog] = None

        # UI Setup
        self._create_header()
        self._create_input_section()
        self._create_action_section()
        self._create_progress_section()
        self._create_footer_section()

    def _create_header(self) -> None:
        """Top Header Banner."""
        header_frame = ctk.CTkFrame(self, corner_radius=10, fg_color="#1E1E2E")
        header_frame.pack(fill="x", padx=15, pady=(15, 10))

        title_label = ctk.CTkLabel(
            header_frame,
            text="🎵 Music Agent",
            font=ctk.CTkFont(family="Segoe UI", size=26, weight="bold"),
            text_color="#89B4FA",
        )
        title_label.pack(side="left", padx=20, pady=12)

        self.update_btn = ctk.CTkButton(
            header_frame,
            text="🔄 Update",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            width=100,
            height=32,
            fg_color="#313244",
            hover_color="#45475A",
            text_color="#CDD6F4",
            corner_radius=8,
            command=self._check_update_click,
        )
        self.update_btn.pack(side="right", padx=(5, 20), pady=12)

        self.logs_btn = ctk.CTkButton(
            header_frame,
            text="📑 Logs",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            width=100,
            height=32,
            fg_color="#313244",
            hover_color="#45475A",
            text_color="#CDD6F4",
            corner_radius=8,
            command=self._open_logs_modal,
        )
        self.logs_btn.pack(side="right", padx=(5, 5), pady=12)

    def _create_input_section(self) -> None:
        """Main Song Input Card."""
        input_frame = ctk.CTkFrame(self, corner_radius=10)
        input_frame.pack(fill="both", expand=False, padx=15, pady=5)

        lbl = ctk.CTkLabel(
            input_frame,
            text="Enter song names (one per line):",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color="#CDD6F4",
        )
        lbl.pack(anchor="w", padx=15, pady=(10, 5))

        self.textbox = ctk.CTkTextbox(
            input_frame,
            height=130,
            font=ctk.CTkFont(family="Consolas", size=14),
            corner_radius=8,
            fg_color="#11111B",
            border_color="#313244",
            border_width=1,
            text_color="#CDD6F4",
        )
        self.textbox.pack(fill="x", padx=15, pady=(0, 10))

        # Quick action buttons for input
        btn_row = ctk.CTkFrame(input_frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=15, pady=(0, 10))

        clear_btn = ctk.CTkButton(
            btn_row,
            text="Clear",
            width=90,
            height=28,
            fg_color="#313244",
            hover_color="#45475A",
            text_color="#CDD6F4",
            command=self._clear_input,
        )
        clear_btn.pack(side="left")

    def _create_action_section(self) -> None:
        """Main Download Action Button."""
        action_frame = ctk.CTkFrame(self, fg_color="transparent")
        action_frame.pack(fill="x", padx=15, pady=8)

        self.download_btn = ctk.CTkButton(
            action_frame,
            text="🚀 Start Download",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            height=45,
            corner_radius=10,
            fg_color="#1E66F5",
            hover_color="#3B82F6",
            command=self._start_download_click,
        )
        self.download_btn.pack(fill="x")

    def _create_progress_section(self) -> None:
        """Progress bar and song status list."""
        progress_frame = ctk.CTkFrame(self, corner_radius=10)
        progress_frame.pack(fill="both", expand=True, padx=15, pady=5)

        # Progress header
        self.status_lbl = ctk.CTkLabel(
            progress_frame,
            text="Ready",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color="#89B4FA",
        )
        self.status_lbl.pack(anchor="w", padx=15, pady=(10, 2))

        self.progress_bar = ctk.CTkProgressBar(
            progress_frame,
            height=12,
            corner_radius=6,
            progress_color="#a6e3a1",
            fg_color="#313244",
        )
        self.progress_bar.set(0.0)
        self.progress_bar.pack(fill="x", padx=15, pady=(2, 10))

        # Scrollable list for individual song statuses
        self.songs_scroll = ctk.CTkScrollableFrame(
            progress_frame,
            label_text="Live Status",
            label_font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="#11111B",
            corner_radius=8,
        )
        self.songs_scroll.pack(fill="both", expand=True, padx=15, pady=(0, 10))

    def _create_footer_section(self) -> None:
        """Bottom Footer Bar with folder button and time counter."""
        footer_frame = ctk.CTkFrame(self, corner_radius=10, fg_color="#1E1E2E")
        footer_frame.pack(fill="x", padx=15, pady=(5, 15))

        self.timer_lbl = ctk.CTkLabel(
            footer_frame,
            text="⏱️ Elapsed Time: 00:00",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color="#BAC2DE",
        )
        self.timer_lbl.pack(side="left", padx=20, pady=10)

        open_dir_btn = ctk.CTkButton(
            footer_frame,
            text="📁 Open Music Folder",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            height=32,
            fg_color="#313244",
            hover_color="#45475A",
            text_color="#CDD6F4",
            command=self._open_music_folder,
        )
        open_dir_btn.pack(side="right", padx=20, pady=10)

    def _clear_input(self) -> None:
        """Clear textbox content."""
        self.textbox.delete("1.0", "end")

    def _open_music_folder(self) -> None:
        """Open the Music output folder in Windows File Explorer."""
        MUSIC_DIR.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(str(MUSIC_DIR))
        elif sys.platform == "darwin":
            import subprocess
            subprocess.run(["open", str(MUSIC_DIR)], check=False)
        else:
            import subprocess
            subprocess.run(["xdg-open", str(MUSIC_DIR)], check=False)

    def _check_update_click(self) -> None:
        """Fetch latest changes from GitHub repository."""
        self.update_btn.configure(state="disabled", text="⏳ Checking...")
        threading.Thread(target=self._run_git_update_bg, daemon=True).start()

    def _run_git_update_bg(self) -> None:
        import io
        import shutil
        import subprocess
        import urllib.request
        import zipfile

        # Method 1: If git directory exists, try git pull first
        git_dir = ROOT / ".git"
        if git_dir.exists():
            try:
                env = dict(os.environ)
                env["GIT_TERMINAL_PROMPT"] = "0"
                res = subprocess.run(
                    ["git", "pull"],
                    cwd=str(ROOT),
                    capture_output=True,
                    text=True,
                    timeout=30,
                    env=env,
                )
                out = (res.stdout or res.stderr or "").strip()
                if "Already up to date" in out or "Already up-to-date" in out:
                    self.after(0, lambda: self._on_update_result("✅ Up to date", "✨ App is already up to date!", "#a6e3a1"))
                    return
                elif res.returncode == 0:
                    self.after(0, lambda: self._on_update_result("✅ Updated!", "✨ App updated successfully from GitHub!", "#a6e3a1"))
                    return
            except Exception:
                pass  # Fall back to direct ZIP download below

        # Method 2: Direct HTTP download from public GitHub repo (works on any PC without git!)
        try:
            repo_zip_url = "https://github.com/abdallasamida10/Music-Agent-/archive/refs/heads/main.zip"
            req = urllib.request.Request(
                repo_zip_url,
                headers={"User-Agent": "MusicAgent-Updater/1.0"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                zip_bytes = resp.read()

            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                namelist = zf.namelist()
                if not namelist:
                    raise RuntimeError("Downloaded ZIP is empty")
                top_prefix = namelist[0].split("/")[0] + "/"

                updated_files = 0
                for member in zf.infolist():
                    rel_path = member.filename
                    if not rel_path.startswith(top_prefix):
                        continue
                    clean_rel = rel_path[len(top_prefix):]
                    if not clean_rel or member.is_dir():
                        continue

                    # Protect user data and local environment folders from being overwritten
                    skip_prefixes = ("Music/", ".venv/", ".cache/", ".playwright-browsers/", "dist/", "build/")
                    if any(clean_rel.startswith(sp) for sp in skip_prefixes):
                        continue
                    if clean_rel == "MusicAgent.exe":
                        continue

                    target_file = ROOT / clean_rel
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(member) as src_file, open(target_file, "wb") as dst_file:
                        shutil.copyfileobj(src_file, dst_file)
                    updated_files += 1

            self.after(0, lambda: self._on_update_result("✅ Updated!", f"✨ Updated from GitHub repository ({updated_files} files)!", "#a6e3a1"))
        except Exception as e:
            self.after(0, lambda: self._on_update_result("❌ Error", f"Update error: {e}", "#f38ba8"))

    def _on_update_result(self, btn_text: str, status_text: str, color: str) -> None:
        self.update_btn.configure(text=btn_text)
        self.status_lbl.configure(text=status_text, text_color=color)

        def _clear_update_status() -> None:
            self.update_btn.configure(state="normal", text="🔄 Update")
            if not self.is_downloading:
                self.status_lbl.configure(text="Ready", text_color="#89B4FA")

        self.after(7000, _clear_update_status)


    def _start_download_click(self) -> None:
        """Handler when user clicks Start Download."""
        if self.is_downloading:
            return

        raw_text = self.textbox.get("1.0", "end").strip()
        lines = [line.strip() for line in raw_text.splitlines() if line.strip() and not line.strip().startswith("#")]

        if not lines:
            self.status_lbl.configure(text="⚠️ Please enter at least one song name!", text_color="#f38ba8")
            return

        # Disable buttons and start state
        self.is_downloading = True
        self.download_btn.configure(state="disabled", text="⏳ Downloading at maximum speed...", fg_color="#585b70")
        self.progress_bar.set(0.0)
        self.status_lbl.configure(text="Preparing download...", text_color="#89B4FA")

        # Clear scroll frame widgets
        for widget in self.songs_scroll.winfo_children():
            widget.destroy()
        self.song_widgets.clear()

        # Extract songs silently check
        armed, songs = extract_from_user_list(lines)
        if not armed or not songs:
            # Silent refusal
            self.status_lbl.configure(text=f"❌ {REFUSAL_MESSAGE}", text_color="#f38ba8")
            self._reset_download_state()
            return

        # Populate song items in UI scroll view
        for song in songs:
            card = ctk.CTkFrame(self.songs_scroll, fg_color="#1E1E2E", corner_radius=6)
            card.pack(fill="x", padx=5, pady=3)

            name_lbl = ctk.CTkLabel(
                card,
                text=song,
                font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                anchor="w",
                text_color="#CDD6F4",
            )
            name_lbl.pack(side="left", padx=10, pady=8)

            badge_lbl = ctk.CTkLabel(
                card,
                text="⏳ Pending...",
                font=ctk.CTkFont(family="Segoe UI", size=12),
                text_color="#fab387",
            )
            badge_lbl.pack(side="right", padx=10, pady=8)

            self.song_widgets[song] = {"card": card, "status": badge_lbl}

        # Smart performance mode: use fast yt-dlp if FFmpeg is installed, otherwise allow ytmp3vid web converter
        has_ffmpeg = bool(shutil.which("ffmpeg"))
        skip_ytmp3 = has_ffmpeg
        max_workers = 50

        self.start_time = time.time()

        # Start timer tick
        self._update_timer()

        # Start background download thread
        self.download_thread = threading.Thread(
            target=self._run_download_bg,
            args=(lines, MUSIC_DIR, skip_ytmp3, max_workers, songs),
            daemon=True,
        )
        self.download_thread.start()

    def _update_timer(self) -> None:
        """Live timer ticker."""
        if not self.is_downloading:
            return
        elapsed = time.time() - self.start_time
        mins, secs = divmod(int(elapsed), 60)
        self.timer_lbl.configure(text=f"⏱️ Elapsed Time: {mins:02d}:{secs:02d}")
        self.after(1000, self._update_timer)

    def _gui_log(self, msg: str) -> None:
        """Thread-safe logging callback passed to process_all."""
        def _apply() -> None:
            for song, widgets in self.song_widgets.items():
                if song in msg or song.casefold() in msg.casefold():
                    if "OK (" in msg or "already exists" in msg or "already saved" in msg:
                        widgets["status"].configure(text="✅ Completed", text_color="#a6e3a1")
                    elif "FAIL" in msg:
                        widgets["status"].configure(text="❌ Failed", text_color="#f38ba8")
                    elif "Searching" in msg or "searching" in msg.lower():
                        widgets["status"].configure(text="🔍 Searching...", text_color="#89B4FA")
                        self.status_lbl.configure(text=f"🔍 Searching: {song}", text_color="#89B4FA")
                    elif "⚡" in msg or "Downloading" in msg or "downloading" in msg.lower():
                        if "(" in msg and ")" in msg:
                            detail = msg[msg.find("(")+1 : msg.find(")")]
                            widgets["status"].configure(text=f"⚡ {detail}", text_color="#f9e2af")
                            self.status_lbl.configure(text=f"⚡ Downloading: {song} ({detail})", text_color="#f9e2af")
                        else:
                            widgets["status"].configure(text="⚡ Downloading...", text_color="#f9e2af")
                            self.status_lbl.configure(text=f"⚡ Downloading: {song}", text_color="#f9e2af")

        self.after(0, _apply)

    def _run_download_bg(
        self,
        raw_lines: List[str],
        music_dir: Path,
        skip_ytmp3: bool,
        max_workers: int,
        songs: List[str],
    ) -> None:
        """Runs in background thread to keep GUI responsive."""
        try:
            total_songs = len(songs)
            completed_count = 0

            def custom_log(msg: str) -> None:
                nonlocal completed_count
                self._gui_log(msg)
                if "OK (" in msg or "already exists" in msg or "already saved" in msg or "FAIL" in msg:
                    completed_count = min(completed_count + 1, total_songs)
                    progress_val = completed_count / total_songs if total_songs > 0 else 1.0
                    self.after(0, lambda p=progress_val, c=completed_count, t=total_songs: self._update_progress(p, c, t))

            results, elapsed = process_all(
                raw_lines,
                music_dir,
                log=custom_log,
                skip_ytmp3=skip_ytmp3,
                max_workers=max_workers,
            )

            self.after(0, lambda: self._on_download_finished(results, elapsed, songs))
        except Exception as exc:
            err_msg = f"Error: {exc}"
            self.after(0, lambda: self._on_download_error(err_msg))

    def _update_progress(self, val: float, done: int, total: int) -> None:
        self.progress_bar.set(val)
        self.status_lbl.configure(
            text=f"Downloading... ({done}/{total})",
            text_color="#89B4FA",
        )

    def _on_download_finished(self, results: List[dict], elapsed: float, songs: List[str]) -> None:
        self.progress_bar.set(1.0)
        mins, secs = divmod(int(elapsed), 60)
        time_str = f"{mins:02d}:{secs:02d}"

        # Update remaining song badges based on results
        success_count = 0
        for r in results:
            q = r.get("query")
            ok = r.get("ok", False)
            if q in self.song_widgets:
                if ok:
                    success_count += 1
                    self.song_widgets[q]["status"].configure(text="✅ Completed", text_color="#a6e3a1")
                else:
                    self.song_widgets[q]["status"].configure(text="❌ Failed", text_color="#f38ba8")

        if success_count == len(songs) and len(songs) > 0:
            self.status_lbl.configure(
                text=f"✨ All downloads completed successfully ({success_count}/{len(songs)}) in {time_str}!",
                text_color="#a6e3a1",
            )
        else:
            self.status_lbl.configure(
                text=f"⚠️ Downloads finished: {success_count} of {len(songs)} succeeded in {time_str}",
                text_color="#f9e2af",
            )

        self._reset_download_state()

    def _on_download_error(self, error_msg: str) -> None:
        """Called when background download thread crashes."""
        self.progress_bar.set(0.0)
        self.status_lbl.configure(
            text=f"❌ {error_msg}",
            text_color="#f38ba8",
        )
        # Mark all pending songs as failed
        for song, widgets in self.song_widgets.items():
            current = widgets["status"].cget("text")
            if "✅" not in current:
                widgets["status"].configure(text="❌ Error", text_color="#f38ba8")
        self._reset_download_state()

    def _reset_download_state(self) -> None:
        self.is_downloading = False
        self.download_btn.configure(
            state="normal",
            text="🚀 Start Download",
            fg_color="#1E66F5",
        )

    def _open_logs_modal(self) -> None:
        """Open or focus the Error Tracking & Logs Toplevel window."""
        if self.logs_window is None or not self.logs_window.winfo_exists():
            self.logs_window = LogsDialog(self)
        else:
            self.logs_window.lift()
            self.logs_window.focus_force()


class LogsDialog(ctk.CTkToplevel):
    def __init__(self, parent: ctk.CTk) -> None:
        super().__init__(parent)

        self.title("📋 Error Tracking & Application Logs")
        self.geometry("780x580")
        self.minsize(680, 480)

        # Bring window to front
        self.after(10, self.lift)
        self.after(20, self.focus_force)

        self._filter_mode = "ALL"

        self._create_header_card()
        self._create_filter_bar()
        self._create_log_view()
        self._create_footer_bar()

        self._refresh_logs()

    def _create_header_card(self) -> None:
        card = ctk.CTkFrame(self, corner_radius=10, fg_color="#1E1E2E")
        card.pack(fill="x", padx=15, pady=(15, 5))

        title_lbl = ctk.CTkLabel(
            card,
            text="💻 Diagnostic & Error Tracking",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color="#89B4FA",
        )
        title_lbl.pack(anchor="w", padx=15, pady=(10, 4))

        info = get_system_info()
        err_count, warn_count = get_error_counts()

        info_text = (
            f"OS: {info.get('OS', 'Unknown')}  |  Python: {info.get('Python', 'Unknown')}  |  "
            f"FFmpeg: {info.get('FFmpeg', 'Unknown')}  |  yt-dlp: {info.get('yt-dlp', 'Unknown')}\n"
            f"Logged in session: {err_count} Error(s), {warn_count} Warning(s)."
        )

        sub_lbl = ctk.CTkLabel(
            card,
            text=info_text,
            font=ctk.CTkFont(family="Consolas", size=12),
            text_color="#BAC2DE",
            justify="left",
        )
        sub_lbl.pack(anchor="w", padx=15, pady=(0, 10))

    def _create_filter_bar(self) -> None:
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=15, pady=5)

        lbl = ctk.CTkLabel(
            bar,
            text="Filter Level:",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#CDD6F4",
        )
        lbl.pack(side="left", padx=(0, 10))

        self.btn_all = ctk.CTkButton(
            bar,
            text="All Logs",
            width=80,
            height=28,
            fg_color="#1E66F5",
            hover_color="#3B82F6",
            command=lambda: self._set_filter("ALL"),
        )
        self.btn_all.pack(side="left", padx=3)

        self.btn_err = ctk.CTkButton(
            bar,
            text="❌ Errors Only",
            width=100,
            height=28,
            fg_color="#313244",
            hover_color="#45475A",
            command=lambda: self._set_filter("ERROR"),
        )
        self.btn_err.pack(side="left", padx=3)

        self.btn_warn = ctk.CTkButton(
            bar,
            text="⚠️ Warnings",
            width=90,
            height=28,
            fg_color="#313244",
            hover_color="#45475A",
            command=lambda: self._set_filter("WARNING"),
        )
        self.btn_warn.pack(side="left", padx=3)

    def _create_log_view(self) -> None:
        self.textbox = ctk.CTkTextbox(
            self,
            font=ctk.CTkFont(family="Consolas", size=12),
            corner_radius=8,
            fg_color="#11111B",
            border_color="#313244",
            border_width=1,
            text_color="#CDD6F4",
        )
        self.textbox.pack(fill="both", expand=True, padx=15, pady=5)

    def _create_footer_bar(self) -> None:
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=15, pady=(5, 15))

        copy_btn = ctk.CTkButton(
            footer,
            text="📋 Copy Logs",
            width=100,
            height=30,
            fg_color="#313244",
            hover_color="#45475A",
            command=self._copy_logs,
        )
        copy_btn.pack(side="left", padx=5)

        folder_btn = ctk.CTkButton(
            footer,
            text="📁 Open Logs Folder",
            width=140,
            height=30,
            fg_color="#313244",
            hover_color="#45475A",
            command=self._open_logs_folder,
        )
        folder_btn.pack(side="left", padx=5)

        clear_btn = ctk.CTkButton(
            footer,
            text="🗑️ Clear Logs",
            width=100,
            height=30,
            fg_color="#f38ba8",
            hover_color="#e64553",
            text_color="#11111B",
            command=self._clear_logs_click,
        )
        clear_btn.pack(side="right", padx=5)

        refresh_btn = ctk.CTkButton(
            footer,
            text="🔄 Refresh",
            width=90,
            height=30,
            fg_color="#313244",
            hover_color="#45475A",
            command=self._refresh_logs,
        )
        refresh_btn.pack(side="right", padx=5)

        self.status_lbl = ctk.CTkLabel(
            footer,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#a6e3a1",
        )
        self.status_lbl.pack(side="right", padx=10)

    def _set_filter(self, mode: str) -> None:
        self._filter_mode = mode
        self.btn_all.configure(fg_color="#1E66F5" if mode == "ALL" else "#313244")
        self.btn_err.configure(fg_color="#1E66F5" if mode == "ERROR" else "#313244")
        self.btn_warn.configure(fg_color="#1E66F5" if mode == "WARNING" else "#313244")
        self._refresh_logs()

    def _refresh_logs(self) -> None:
        raw_text = read_logs()
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")

        if self._filter_mode == "ALL":
            self.textbox.insert("1.0", raw_text)
        else:
            filtered_lines = []
            for line in raw_text.splitlines():
                if self._filter_mode == "ERROR" and (" [ERROR] " in line or " [CRITICAL] " in line or "Traceback" in line):
                    filtered_lines.append(line)
                elif self._filter_mode == "WARNING" and " [WARNING] " in line:
                    filtered_lines.append(line)
            display_text = "\n".join(filtered_lines) if filtered_lines else f"No logs matching filter level '{self._filter_mode}'."
            self.textbox.insert("1.0", display_text)

        self.textbox.see("end")
        self.textbox.configure(state="disabled")

    def _copy_logs(self) -> None:
        content = self.textbox.get("1.0", "end").strip()
        self.clipboard_clear()
        self.clipboard_append(content)
        self.status_lbl.configure(text="Copied to clipboard!")
        self.after(3000, lambda: self.status_lbl.configure(text=""))

    def _open_logs_folder(self) -> None:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(str(LOGS_DIR))
        elif sys.platform == "darwin":
            import subprocess
            subprocess.run(["open", str(LOGS_DIR)], check=False)
        else:
            import subprocess
            subprocess.run(["xdg-open", str(LOGS_DIR)], check=False)

    def _clear_logs_click(self) -> None:
        clear_logs()
        self._refresh_logs()
        self.status_lbl.configure(text="Logs cleared!")
        self.after(3000, lambda: self.status_lbl.configure(text=""))


def main() -> int:
    app = MusicAgentApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
