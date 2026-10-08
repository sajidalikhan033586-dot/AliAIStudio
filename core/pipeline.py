"""End-to-end clip pipeline: moments -> captions -> voiceover -> render.

Runs in a worker thread. All UI updates go through the callbacks, which the
screen marshals onto the GUI thread with .after().
"""
import tempfile
import threading
import traceback
from pathlib import Path

from core.captions import build_ass, PRESETS
from core.render import render_clip, RenderError
from core.voiceover import synthesize, VoiceoverError
import logging

log = logging.getLogger("ali_ai_studio")


class PipelineCancelled(Exception):
    pass


def _check(cancel_event):
    if cancel_event is not None and cancel_event.is_set():
        raise PipelineCancelled()


def run_pipeline(app, video_path: str, moments: list, options: dict,
                 progress_cb, status_cb, done_cb, cancel_event) -> threading.Thread:
    """
    options: {
      "captions": True/False, "caption_preset": "tiktok",
      "voiceover": None | voice_id, "audio_mode": "keep"|"duck"|"replace",
      "fmt": "9:16"|"16:9",
    }
    done_cb(ok: bool, message: str, out_files: list)
    """
    def _work():
        out_files = []
        try:
            _run(app, video_path, moments, options,
                 progress_cb, status_cb, cancel_event, out_files)
            done_cb(True, f"{len(out_files)} clips ready!", out_files)
        except PipelineCancelled:
            done_cb(False, "Cancelled.", out_files)
        except (RenderError, VoiceoverError) as exc:
            log.error("pipeline failed: %s", exc)
            done_cb(False, str(exc), out_files)
        except Exception:
            log.error("pipeline crashed:\n%s", traceback.format_exc())
            done_cb(False, "Something went wrong. Details saved to error_log.txt.",
                    out_files)

    t = threading.Thread(target=_work, daemon=True)
    t.start()
    return t


def _run(app, video_path, moments, options,
         progress_cb, status_cb, cancel_event, out_files):
    stem = Path(video_path).stem[:40] or "video"
    out_dir = app.app_dir / "Clips" / "".join(
        c if c.isalnum() or c in " _-" else "_" for c in stem).strip()
    out_dir.mkdir(parents=True, exist_ok=True)
    tmpdir = Path(tempfile.mkdtemp(prefix="aas_clip_"))
    fmt = options.get("fmt", "9:16")
    suffix = "9x16" if fmt == "9:16" else "16x9"

    total = max(1, len(moments))
    for i, m in enumerate(moments):
        _check(cancel_event)
        base = f"clip_{i+1:02d}_{suffix}"
        status_cb(f"Clip {i+1}/{total}: preparing...")

        # 1. captions
        ass_path = None
        if options.get("captions", True):
            _check(cancel_event)
            status_cb(f"Clip {i+1}/{total}: making captions...")
            ass_text = build_ass(app.transcript["segments"], m["start"], m["end"],
                                 options.get("caption_preset", "tiktok"))
            ass_path = tmpdir / f"{base}.ass"
            ass_path.write_text(ass_text, encoding="utf-8")

        # 2. voiceover (skipped when the moment has no speech text,
        #    e.g. energy-picked music parts - original audio is kept)
        vo_path = None
        voice = options.get("voiceover")
        vo_text = (m.get("text") or "").strip()
        if voice and not vo_text:
            status_cb(f"Clip {i+1}/{total}: no speech here - keeping original audio.")
            voice = None
        audio_mode = options.get("audio_mode", "keep")
        if voice is None:
            audio_mode = "keep"
        if voice:
            _check(cancel_event)
            status_cb(f"Clip {i+1}/{total}: generating AI voice...")
            vo_path = str(tmpdir / f"{base}_vo.mp3")
            synthesize(vo_text, voice, vo_path,
                       cancel_event=cancel_event)

        # 3. render
        _check(cancel_event)
        status_cb(f"Clip {i+1}/{total}: rendering video...")
        def _pc(frac, _i=i):
            try:
                progress_cb((_i + frac) / total)
            except Exception:
                pass
        out_path = str(out_dir / f"{base}.mp4")
        render_clip(video_path, m["start"], m["end"], out_path, fmt=fmt,
                    ass_path=str(ass_path) if ass_path else None,
                    voiceover_path=vo_path,
                    audio_mode=audio_mode,
                    progress_cb=_pc, cancel_event=cancel_event,
                    status_cb=status_cb)
        out_files.append(out_path)

    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)
    status_cb("All clips exported!")
