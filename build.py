#!/usr/bin/env python3
"""
Cross-Platform Build Script for Music Agent
-------------------------------------------
Builds a standalone executable using PyInstaller.
- On Windows: outputs MusicAgent.exe
- On macOS: outputs MusicAgent (binary)
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent

if sys.platform == "win32":
    for stream in (sys.stdout, sys.stderr):
        if stream is not None:
            try:
                stream.reconfigure(encoding="utf-8")
            except Exception:
                pass

def get_customtkinter_path() -> Path:
    import customtkinter
    return Path(customtkinter.__file__).parent

def main() -> int:
    print(f"[*] Building Music Agent on platform: {sys.platform}")

    ctk_path = get_customtkinter_path()
    print(f"[*] Found CustomTkinter assets at: {ctk_path}")

    sep = ";" if sys.platform == "win32" else ":"
    add_data_ctk = f"{ctk_path}{sep}customtkinter"

    app_name = "MusicAgent"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name", app_name,
        "--add-data", add_data_ctk,
        "--hidden-import", "customtkinter",
        "--hidden-import", "yt_dlp",
        "--hidden-import", "rich",
        "--hidden-import", "PIL",
        "--hidden-import", "src.logger",
        "--exclude-module", "playwright",
        "--clean",
        str(ROOT / "agent.py"),
    ]

    print(f"[*] Command: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(ROOT))

    if result.returncode == 0:
        dist_dir = ROOT / "dist" / app_name
        if dist_dir.exists():
            print(f"[OK] Successfully created standalone folder bundle: {dist_dir}")
            # Zip the directory with top-level folder inside the archive for easy extraction
            zip_target = ROOT / f"{app_name}-{sys.platform}"
            shutil.make_archive(str(zip_target), "zip", root_dir=ROOT / "dist", base_dir=app_name)
            print(f"[OK] Created distribution package: {zip_target}.zip")
    else:
        print("[FAIL] Build failed!")

    return result.returncode

if __name__ == "__main__":
    raise SystemExit(main())
