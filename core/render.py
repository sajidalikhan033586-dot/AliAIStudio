"""Render final clips with ffmpeg (bundled, no extra installs).

- 9:16: center crop to vertical + upscale to 1080x1920.
- 16:9: scale to 1920x1080.
- Karaoke captions burned in with the libass filter.
- Audio: keep original / duck under AI voiceover / replace with voiceover.
"""
import re
import subprocess
import threading
from pathlib import Path

from core.media import get_ffmpeg_exe


class RenderError(Exception):
    """User-friendly render failure."""


def _escape_sub_path(path: str) -> str:
    """Escape a subtitle file path for ffmpeg's filter parser."""
    p = path.replace("\\", "/").replace(":", "\\:")
    return f"'{p}'"


def _has_audio(src: str) -> bool:
    exe = get_ffmpeg_exe()
    r = subprocess.run([exe, "-hide_banner", "-i", src],
                       capture_output=True, text=True)
    return bool(re.search(r"Stream.*Audio", r.stderr))


def render_clip(src_video: str, start: float, end: float, out_path: str,
                fmt: str = "9:16", ass_path: str | None = None,
                voiceover_path: str | None = None, audio_mode: str = "keep",
                progress_cb=None, cancel_event=None,
                status_cb=None) -> str:
    """
    Render one clip. progress_cb(fraction 0..1). Returns out_path.
    audio_mode: "keep" | "duck" | "replace" (duck/replace need voiceover_path).
    """
    dur = max(1.0, end - start)
    exe = get_ffmpeg_exe()
    say = status_cb or (lambda _t: None)

    if fmt == "9:16":
        vchain = "crop=ih*9/16:ih:(iw-ow)/2:0,scale=1080:1920"
    else:
        vchain = "scale=1920:1080"
    if ass_path:
        vchain += f",subtitles={_escape_sub_path(ass_path)}"

    use_vo = voiceover_path and audio_mode in ("duck", "replace")
    if use_vo and not Path(voiceover_path).exists():
        use_vo = False

    cmd = [exe, "-y", "-v", "error", "-progress", "pipe:1", "-nostats",
           "-ss", f"{start:.2f}", "-t", f"{dur:.2f}", "-i", src_video]
    if use_vo:
        cmd += ["-i", voiceover_path]

    if not _has_audio(src_video) and not use_vo:
        # rare: video without any audio track
        fc = f"[0:v]{vchain}[v]"
        amap = []
    elif audio_mode == "replace" and use_vo:
        fc = (f"[0:v]{vchain}[v];"
              f"[1:a]apad,atrim=0:{dur:.2f}[a]")
        amap = ["-map", "[a]"]
    elif audio_mode == "duck" and use_vo:
        fc = (f"[0:v]{vchain}[v];"
              f"[0:a]volume=0.25[a1];"
              f"[1:a]apad,atrim=0:{dur:.2f}[a2];"
              f"[a1][a2]amix=inputs=2:duration=first:dropout_transition=0[a]")
        amap = ["-map", "[a]"]
    else:
        fc = f"[0:v]{vchain}[v];[0:a]anull[a]"
        amap = ["-map", "[a]"]

    cmd += ["-filter_complex", fc, "-map", "[v]"] + amap + [
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart", out_path]

    def _cancelled():
        return cancel_event is not None and cancel_event.is_set()

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True,
                                bufsize=1)
    except Exception as exc:
        raise RenderError(f"Could not start video rendering: {exc}") from exc

    try:
        out_ms = 0
        for line in proc.stdout:
            if _cancelled():
                proc.kill()
                raise RenderError("Cancelled.")
            m = re.match(r"out_time_ms=(\d+)", line.strip())
            if m and progress_cb:
                frac = min(0.99, int(m.group(1)) / 1_000_000 / dur)
                try:
                    progress_cb(frac)
                except Exception:
                    pass
        proc.wait()
    finally:
        if proc.poll() is None:
            proc.kill()

    if _cancelled():
        raise RenderError("Cancelled.")
    if proc.returncode != 0:
        raise RenderError(
            "Video rendering failed. The source file may be damaged - "
            "try a different video (MP4 works best).")
    if progress_cb:
        try:
            progress_cb(1.0)
        except Exception:
            pass
    say(f"Saved: {Path(out_path).name}")
    return out_path


def render_clip_threaded(*args, **kwargs):
    """Run render_clip in a daemon thread. Returns the Thread."""
    t = threading.Thread(target=render_clip, args=args, kwargs=kwargs,
                         daemon=True)
    t.start()
    return t
