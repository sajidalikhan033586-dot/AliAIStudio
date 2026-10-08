# Ali AI Studio — Free AI Clipper for Creators

**v0.3.0 — the full app:** video in → AI finds viral moments → karaoke
captions → optional AI voiceover → 9:16/16:9 clips out.
100% free, offline-first.

## Easiest way (no Python needed)

Every push to this repo auto-builds a ready **AliAIStudio.exe**:
**Actions tab → latest build → Artifacts → AliAIStudio-Windows.**
Download, extract, double-click. (Windows shows a SmartScreen warning for
unsigned apps — More info → Run anyway.)

## Run from source (Windows)

You need **Python 3.10 or newer** from [python.org](https://www.python.org/downloads/).
During install, tick **"Add python.exe to PATH"**. Then:
```
pip install -r requirements.txt
python app.py
```

## How it works

1. **Add a video** — drag & drop / Browse from your computer, or paste a
   YouTube / TikTok link (it downloads automatically, max 720p to stay fast).
2. **Adjust settings** — clips (default 2), length (default 60s, up to 3 min),
   format (9:16 default, 16:9 optional), English captions on/off.
3. **Find Viral Clips** — the app transcribes speech offline, finds the best
   moments with scores + reasons, and lets you pick which ones to keep.
4. **Make it yours** — karaoke caption styles, AI voiceover (US male/female
   with preview), keep / duck / replace the original audio.
5. **Generate** — exports 1080p MP4 clips to your Clips folder.

Notes:
- First transcription downloads a small speech model (~75MB, one-time).
  After that, everything works **offline** (voiceover needs internet).
- If a TikTok link fails (TikTok sometimes blocks downloaders), the app
  tells you to download the video and add it from your computer instead.

**Smart Mode (optional):** add a free Gemini API key and the app sends only
the transcript *text* (never your video) to Google for better moment picks.
Without a key, everything still works in Free Mode.

## If something goes wrong

1. The app shows a popup: **"Something went wrong"**.
2. Press **"Copy error details"** and send the text to support.
3. The full log is always at: `%APPDATA%\AliAIStudio\error_log.txt`
   (paste that into the Run box / File Explorer address bar)

## Privacy & security (short version)

- API keys are stored **only on your own PC** (`%APPDATA%\AliAIStudio\config.json`),
  obfuscated (not plain text). They are sent **only to Google**, and only in Smart Mode.
- **Your videos never leave your PC.** Nothing is uploaded or collected.
  Links you paste are only used to download the video.
- Error reports are **never** sent automatically — you copy & send them yourself.
- `config.json` is outside this repo, so keys can never leak through GitHub.

## Project layout

```
AliAIStudio/
├── app.py            ← start here (main window)
├── run.bat           ← double-click starter for Windows
├── requirements.txt  ← free libraries
├── screens/          ← welcome, keys, dashboard, analyze, settings (what you SEE)
├── core/             ← transcribe, moments, captions, voiceover, render, pipeline (what WORKS)
└── assets/           ← logo, Theme A (Midnight Cyan)
```
