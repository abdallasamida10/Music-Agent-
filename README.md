# 🎵 Music Download Agent

A fast, cross-platform application that converts song names (English or **Arabic**) to high-quality **MP3** files saved into your `Music/` folder.

Supports both **Windows** (`MusicAgent.exe`) and **macOS** (`MusicAgent`).

---

## ⚡ Quick Start

### 🪟 Windows Users
1. Download `MusicAgent.exe` from [GitHub Releases](https://github.com/abdallasamida10/Music-Agent-/releases/latest).
2. Double-click `MusicAgent.exe` to open the Graphical User Interface (GUI).
3. Paste song names (one per line) and click **🚀 Start Download**.

### 🍏 macOS Users
1. Download `MusicAgent` from [GitHub Releases](https://github.com/abdallasamida10/Music-Agent-/releases/latest).
2. Open Terminal in the download directory and make it executable:
   ```bash
   chmod +x MusicAgent
   ./MusicAgent
   ```
3. *(If macOS shows a security warning)*: Go to **System Settings > Privacy & Security** and click **Open Anyway**, or run:
   ```bash
   xattr -d com.apple.quarantine MusicAgent
   ```

---

## 🚀 Features

- **Cross-Platform**: Standalone executables for both Windows & macOS — no Python installation needed!
- **High Performance**: Multithreaded parallel processing (downloads multiple songs concurrently).
- **Arabic & UTF-8 Support**: Full support for international title queries and safe file naming.
- **Smart Deduplication**: Automatically skips songs or YouTube video IDs already downloaded.
- **Automatic Output**: All MP3 files are neatly organized inside `./Music/`.

---

## 🛠 System Requirement: FFmpeg

The application relies on `ffmpeg` for extracting and encoding MP3 audio.

- **Windows**: Install via `winget install ffmpeg` or download from [ffmpeg.org](https://ffmpeg.org).
- **macOS**: Install via Homebrew:
  ```bash
  brew install ffmpeg
  ```

---

## 💻 Developer / Building from Source

To build standalone executables locally from source:

```bash
# Install dependencies
pip install -r requirements.txt
pip install pyinstaller

# Run cross-platform build script
python build.py
```

Automated cross-platform builds run on every push to `main` via **GitHub Actions**.

---

## 📄 License
MIT License
