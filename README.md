# Music Download Agent

CLI agent that takes song names (English or **Arabic**), finds them on YouTube, converts to **MP3** (highest quality), and saves files into the `Music` folder.

## How it works

1. You run `start` and send song names.
2. Agent searches YouTube for each name (**exactly 1 video** — top hit only).
3. **Primary:** opens [ytmp3vid.org](https://www.ytmp3vid.org/) and converts at highest quality (320 kbps when available).
4. **Fallback:** if the website fails, downloads with **yt-dlp** + **ffmpeg**.
5. MP3s land in `Music/` — **1 song name → 1 MP3 file** (never 2–3 files for one name).

### One song per name (important)

| Rule | Behavior |
|------|----------|
| 1 name | 1 YouTube result (`ytsearch1`) |
| 1 name | 1 MP3 file, named after your song name |
| Same video twice | Second name is **skipped** if it hits the same video already saved |
| Not done | Chat “simulation” does **not** download — only running `start` / `agent.py` does |

## First-time setup

Open PowerShell in this folder:

```powershell
.\setup.ps1
```

This creates `.venv`, installs `yt-dlp` + `playwright`, and downloads Chromium.

**All installs stay in this project folder** (`.venv`, `.playwright-browsers`, `.cache`) so a full **C:** drive is not used for Playwright (~180 MB Chromium).

Requires: **Python 3**, **ffmpeg** on PATH (already common via Chocolatey/`winget install ffmpeg`).

## Daily use

```bat
start
```

Or:

```powershell
.\start.bat
.\start.ps1
.\.venv\Scripts\python.exe agent.py
```

### After opening (`start.bat`)

```
Write start to begin
>
```

Type **`start`**, then:

```
Send all the music names
  • Paste one song per line, then empty line or 'done'
  • Or type 'one' for one-by-one mode
  • Arabic names supported | 'exit' to quit
```

**Batch example:**

```
Despacito
أم كلثوم الأطلال
Bohemian Rhapsody
done
```

**One-by-one:** type `one`, then enter names after each download; type `done` to finish.

**CLI shortcuts:**

```powershell
.\start.bat "song one" "أغنية"
.\start.bat --one
.\start.bat --skip-ytmp3 "song name"
```

### Environment variables

| Variable     | Meaning                                      |
|--------------|----------------------------------------------|
| `HEADLESS=0` | Show the browser during ytmp3vid automation  |
| `SKIP_YTMP3=1` | Skip website; use yt-dlp only              |

## Output

All files: `Music/` (inside the project folder)

## Notes

- Use only for content you have the right to download/convert.
- Converter websites change often; yt-dlp fallback keeps the agent working.
- Any AI agent (Grok, Claude, Cursor, Codex, …) can operate this project — see **AGENTS.md**.
