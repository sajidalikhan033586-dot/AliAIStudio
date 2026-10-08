"""
Video info via the bundled ffmpeg binary (imageio-ffmpeg, free).

Why imageio-ffmpeg: it ships a static ffmpeg binary inside the pip package,
so students don't need to install or configure ffmpeg separately.
Only the standard library + imageio-ffmpeg is used here (no ffprobe needed:
we parse `ffmpeg -i` output).
"""
import re
import subprocess
from pathlib import Path

_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):([\d.]+)")
_RES_RE = re.compile(r"Stream.*Video:.*?(\d{3,5})x(\d{3,5})")


def get_ffmpeg_exe() -> str:
    """Path to the bundled ffmpeg binary. Raises a friendly error if missing."""
    try:
        import imageio_ffmpeg
    except ImportError as exc:
        raise RuntimeError(
            "ffmpeg is missing. Please run:  pip install -r requirements.txt"
        ) from exc
    return imageio_ffmpeg.get_ffmpeg_exe()


def parse_ffmpeg_info(stderr: str) -> dict:
    """Parse `ffmpeg -i` stderr into duration/resolution. Pure function (testable)."""
    info = {"duration_sec": 0, "width": 0, "height": 0}
    m = _DURATION_RE.search(stderr)
    if m:
        h, mn, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
        info["duration_sec"] = int(h * 3600 + mn * 60 + s)
    m = _RES_RE.search(stderr)
    if m:
        info["width"], info["height"] = int(m.group(1)), int(m.group(2))
    return info


def format_duration(seconds: int) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    mn, s = divmod(rem, 60)
    if h:
        return f"{h}:{mn:02d}:{s:02d}"
    return f"{mn}:{s:02d}"


def get_video_info(path: str) -> dict:
    """
    Returns a dict. On success: {"ok": True, "title", "duration_sec",
    "duration_text", "width", "height", "size_mb", "path"}.
    On failure: {"ok": False, "message": <friendly message>}.
    """
    p = Path(path)
    if not p.is_file():
        return {"ok": False, "message": "File not found. Please choose the video again."}
    try:
        proc = subprocess.run(
            [get_ffmpeg_exe(), "-hide_banner", "-i", str(p)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, timeout=30,
        )
    except FileNotFoundError:
        return {"ok": False, "message": "ffmpeg is missing. Run: pip install -r requirements.txt"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "message": "Could not read the video (timeout). Try another file."}
    except RuntimeError as exc:
        return {"ok": False, "message": str(exc)}

    parsed = parse_ffmpeg_info(proc.stderr or "")
    if parsed["duration_sec"] <= 0:
        return {"ok": False,
                "message": "This file does not look like a video. Please choose an MP4/MOV/WEBM file."}
    size_mb = p.stat().st_size / (1024 * 1024)
    return {
        "ok": True,
        "title": p.stem,
        "duration_sec": parsed["duration_sec"],
        "duration_text": format_duration(parsed["duration_sec"]),
        "width": parsed["width"],
        "height": parsed["height"],
        "size_mb": round(size_mb, 1),
        "path": str(p),
    }
