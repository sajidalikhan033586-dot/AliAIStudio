"""
Video acquisition: local files + YouTube/TikTok links.

- Downloads use yt-dlp (free). Max 720p: small files, fast on slow laptops
  and slow internet — plenty for Shorts/Reels/TikTok.
- TikTok links sometimes fail (TikTok blocks downloaders). That is EXPECTED:
  we show a friendly message asking the user to add the video from the
  computer instead. This is a feature, not a bug.
- The downloader keeps itself fresh: once a day, a background thread tries
  `pip install -U yt-dlp` (best effort, never blocks the UI).
"""
import datetime as dt
import os
import re
import subprocess
import sys
import threading
import urllib.parse
from pathlib import Path

SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v"}

# 720p max: fast downloads, small files — enough for vertical clips.
YT_DLP_FORMAT = "bv*[height<=720]+ba/b[height<=720]/b"


class DownloadCancelled(Exception):
    pass


def detect_source(url_or_path: str) -> str:
    """Return 'youtube' | 'tiktok' | 'local' | 'unsupported'. Pure function (testable)."""
    s = (url_or_path or "").strip()
    if not s:
        return "unsupported"
    low = s.lower()
    if os.path.exists(s) or re.match(r"^[a-zA-Z]:[\\/]", s) or s.startswith("/"):
        return "local"
    try:
        host = urllib.parse.urlparse(s if "://" in s else "https://" + s).netloc.lower()
    except Exception:
        return "unsupported"
    if "youtube.com" in host or "youtu.be" in host:
        return "youtube"
    if "tiktok.com" in host:
        return "tiktok"
    if host and "." in host:
        # Any other link: let yt-dlp try (it supports 1000+ sites).
        return "youtube"
    return "unsupported"


def friendly_dl_error(exc: Exception, source: str) -> str:
    """Map technical errors to friendly user messages. Pure function (testable)."""
    msg = str(exc)
    if isinstance(exc, DownloadCancelled):
        return "Download cancelled."
    if source == "tiktok":
        return ("Could not download this TikTok link (TikTok sometimes blocks "
                "downloaders). Please download the video and add it from your computer.")
    if "Private video" in msg:
        return "This video is private. Please use a public video link."
    if "age" in msg.lower() and "restrict" in msg.lower():
        return "This video is age-restricted and cannot be downloaded. Try another link."
    if "Unsupported URL" in msg:
        return "This link is not supported. Try a YouTube/TikTok link or a file from your computer."
    short = msg.strip().splitlines()[0][:160] if msg.strip() else "unknown error"
    return f"Download failed: {short}"


def ensure_downloader_updated(config: dict) -> None:
    """
    Best-effort background refresh of yt-dlp (once per day).
    Never raises, never blocks the UI — call it in a daemon thread.
    """
    try:
        today = dt.date.today().isoformat()
        if config.get("ytdlp_updated") == today:
            return
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q", "--upgrade", "yt-dlp"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180,
        )
        config["ytdlp_updated"] = today
        from core.config import save_config
        save_config(config)
    except Exception:
        pass  # best effort only


class DownloadManager:
    """Downloads a video link to the app's videos folder (in a worker thread)."""

    def __init__(self, app_dir: Path):
        self.videos_dir = Path(app_dir) / "videos"
        self.videos_dir.mkdir(parents=True, exist_ok=True)

    # ---------- local files ----------
    def check_local_file(self, path: str) -> dict:
        p = Path(path)
        if not p.is_file():
            return {"ok": False, "message": "File not found. Please choose the video again."}
        if p.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return {"ok": False,
                    "message": f"Unsupported file type ({p.suffix}). Use MP4, MOV or WEBM."}
        return {"ok": True, "path": str(p)}

    # ---------- link info (no download) ----------
    def link_info(self, url: str) -> dict:
        try:
            import yt_dlp
        except ImportError:
            return {"ok": False, "message": "Downloader is missing. Run: pip install -r requirements.txt"}
        try:
            with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "noplaylist": True}) as ydl:
                info = ydl.extract_info(url, download=False)
            return {"ok": True,
                    "title": info.get("title") or "Video",
                    "duration_sec": int(info.get("duration") or 0)}
        except Exception as exc:
            return {"ok": False, "message": friendly_dl_error(exc, detect_source(url))}

    # ---------- link download (blocking; run in a thread) ----------
    def download_link(self, url: str, progress_cb, cancel_event: threading.Event) -> dict:
        try:
            import yt_dlp
        except ImportError:
            return {"ok": False, "message": "Downloader is missing. Run: pip install -r requirements.txt"}

        source = detect_source(url)
        out_tmpl = str(self.videos_dir / "%(title).60s [%(id)s].%(ext)s")
        state = {"filename": None}

        def hook(d):
            if cancel_event.is_set():
                raise DownloadCancelled()
            if d.get("status") == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                progress_cb(d.get("downloaded_bytes", 0), total)
            elif d.get("status") == "finished":
                state["filename"] = d.get("filename")

        opts = {"format": YT_DLP_FORMAT, "outtmpl": out_tmpl, "quiet": True,
                "no_warnings": True, "noplaylist": True, "progress_hooks": [hook]}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
            path = state["filename"]
            if not path or not os.path.isfile(path):
                # Fallback: find the newest file in the videos dir.
                files = sorted(self.videos_dir.glob("*"), key=os.path.getmtime)
                path = str(files[-1]) if files else None
            if not path:
                return {"ok": False, "message": friendly_dl_error(Exception("no file"), source)}
            return {"ok": True, "path": path}
        except Exception as exc:
            return {"ok": False, "message": friendly_dl_error(exc, source)}

    def download_in_thread(self, url, progress_cb, done_cb, cancel_event):
        """progress_cb(done_bytes, total_bytes) and done_cb(result_dict) run via UI thread."""
        def worker():
            result = self.download_link(url, progress_cb, cancel_event)
            done_cb(result)
        threading.Thread(target=worker, daemon=True).start()
