@echo off
title Ali AI Studio
cd /d "%~dp0"

python --version >nul 2>&1
if errorlevel 1 (
    echo ============================================================
    echo  Python nahi mila!
    echo  Pehle python.org se Python install karein.
    echo  Install ke waqt "Add python.exe to PATH" par TICK zaroor lagayein.
    echo ============================================================
    pause
    exit /b 1
)

echo Libraries install ho rahi hain (pehli dafa 1-2 minute lag sakta hai)...
pip install -r requirements.txt
echo.
echo Ali AI Studio start ho raha hai...
python app.py
pause
