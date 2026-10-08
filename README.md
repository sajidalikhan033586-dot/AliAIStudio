# Ali AI Studio — Free AI Clipper for Creators

**Module 1:** project setup + welcome screen + Gemini API key manager + error logging.

## Run it (Windows)

**Option A — double click (easiest):** double-click `run.bat`.
It checks Python, installs the free libraries, and starts the app.

**Option B — command line:**
```
pip install -r requirements.txt
python app.py
```

You need **Python 3.10 or newer** from [python.org](https://www.python.org/downloads/).
During install, tick **"Add python.exe to PATH"**.

## If something goes wrong

1. The app shows a popup: **"Something went wrong"**.
2. Press **"Copy error details"** and send the text to support.
3. The full log is always at: `%APPDATA%\AliAIStudio\error_log.txt`
   (paste that into the Run box / File Explorer address bar)

## Privacy & security (short version)

- API keys are stored **only on your own PC** (`%APPDATA%\AliAIStudio\config.json`),
  obfuscated (not plain text). They are sent **only to Google**, and only in Smart Mode.
- **Your videos never leave your PC.** Nothing is uploaded or collected.
- Error reports are **never** sent automatically — you copy & send them yourself.
- `config.json` is outside this repo, so keys can never leak through GitHub.

## Project layout

```
AliAIStudio/
├── app.py            ← start here (main window)
├── run.bat           ← double-click starter for Windows
├── requirements.txt  ← free libraries
├── screens/          ← welcome screen, API key screen  (what you SEE)
├── core/             ← config, key manager, error logger (what WORKS)
└── assets/           ← logo, Theme A (Midnight Cyan)
```

Module 2 will add the dashboard (video input + clip settings).
