"""Local configuration.

Everything is stored on the USER'S OWN PC (Windows: %APPDATA%/AliAIStudio).
Nothing is ever uploaded anywhere. config.json is NOT part of the git repo,
so API keys can never leak through GitHub.
"""
import json
import os
from pathlib import Path

APP_DIR_NAME = "AliAIStudio"
CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "first_run": True,
    "theme": "midnight_cyan",
    "keys": [],                          # obfuscated API keys (see core/keys.py)
    "active_key_index": 0,
    "usage": {"date": "", "calls": 0},   # local daily estimate of API calls
    "clips_count": 2,
    "clip_length": 60,
    "clip_format": "9:16",
    "transcribe_quality": "fast",        # "fast" (tiny) or "accurate" (base)
    "translate_en": True,                # auto-translate captions to English
    "caption_preset": "tiktok",
    "voiceover_voice": "Off",
}


def get_app_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    path = Path(base) / APP_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def _config_path() -> Path:
    return get_app_dir() / CONFIG_FILE


def load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(_config_path(), "r", encoding="utf-8") as f:
            saved = json.load(f)
        cfg.update(saved)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return cfg


def save_config(cfg: dict) -> None:
    tmp = _config_path().with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    os.replace(tmp, _config_path())  # atomic write: never a half-written file
