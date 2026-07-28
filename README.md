# 🎵 Music Download Agent

A fast, cross-platform application that converts song names (English or **Arabic**) to high-quality **MP3** files saved into your `Music/` folder.

Supports both **Windows** (`MusicAgent.exe`) and **macOS** (`MusicAgent`).

---

## ⚡ Detailed Step-by-Step Guide (Baby Steps)

### 🪟 Windows Users

1. **Download the Package**:
   - Go to the [Latest GitHub Release](https://github.com/abdallasamida10/Music-Agent-/releases/latest).
   - Download **`MusicAgent-Windows.zip`**.
2. **Extract the ZIP**:
   - Right-click `MusicAgent-Windows.zip` and select **Extract All...** (or use WinRAR / 7-Zip).
   - Open the extracted folder.
3. **Check FFmpeg Requirement**:
   - FFmpeg is required to process MP3 audio.
   - If you don't have it installed, open Command Prompt or PowerShell and run:
     ```cmd
     winget install ffmpeg
     ```
   - Or place `ffmpeg.exe` directly inside the same folder as `MusicAgent.exe`.
4. **Launch the Application**:
   - Double-click **`MusicAgent.exe`** to open the Graphical User Interface (GUI).
5. **Start Downloading**:
   - Type or paste your song names (one per line — Arabic & English supported).
   - Click **🚀 Start Download**.
   - Your downloaded MP3 files will automatically appear inside the **`Music/`** folder!

---

### 🍏 macOS Users

1. **Download the Package**:
   - Go to the [Latest GitHub Release](https://github.com/abdallasamida10/Music-Agent-/releases/latest).
   - Download **`MusicAgent-macOS.zip`**.
2. **Extract the ZIP**:
   - Double-click `MusicAgent-macOS.zip` to extract the `MusicAgent` binary into your **Downloads** folder.
3. **Install FFmpeg**:
   - Open the **Terminal** app and install FFmpeg using Homebrew:
     ```bash
     brew install ffmpeg
     ```
4. **Make Binary Executable**:
   - In Terminal, navigate to your Downloads directory:
     ```bash
     cd ~/Downloads
     ```
   - Grant execution permission to the binary:
     ```bash
     chmod +x MusicAgent
     ```
5. **Launch & Handle macOS Security Warning**:
   - Launch the app from Terminal:
     ```bash
     ./MusicAgent
     ```
   - **If macOS blocks execution** with *"Developer cannot be verified"* or *"Unidentified Developer"*:
     - **Method A (GUI)**: Open **System Settings ⚙️ > Privacy & Security**, scroll down to the *Security* section, and click **Open Anyway**.
     - **Method B (Terminal Command)**: Remove the quarantine attribute by running:
       ```bash
       xattr -d com.apple.quarantine MusicAgent
       ```
6. **Start Downloading**:
   - Enter your song titles and click **🚀 Start Download**. MP3s will be saved in `./Music/`.

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
