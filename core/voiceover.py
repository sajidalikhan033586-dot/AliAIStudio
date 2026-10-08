"""AI voiceover with edge-tts (Microsoft's free neural voices).

- Needs internet (voices are generated online), but the app itself stays free.
- 4 built-in US voices (2 female, 2 male) + preview before you commit.
- Long texts are split into sentences so no request is too big.
"""
import asyncio
import re

VOICES = [
    ("en-US-AriaNeural", "Aria - Female (US)"),
    ("en-US-JennyNeural", "Jenny - Female (US)"),
    ("en-US-GuyNeural", "Guy - Male (US)"),
    ("en-US-DavisNeural", "Davis - Male (US)"),
]
DEFAULT_VOICE = VOICES[0][0]
PREVIEW_TEXT = "This is how your clips will sound with AI voiceover."


class VoiceoverError(Exception):
    """User-friendly voiceover failure."""


def voice_id_to_label(voice_id: str) -> str:
    for vid, label in VOICES:
        if vid == voice_id:
            return label
    return VOICES[0][1]


def _split_sentences(text: str, max_chars: int = 900) -> list:
    parts = re.split(r"(?<=[.!?])\\s+", text.strip())
    chunks, cur = [], ""
    for p in parts:
        if len(cur) + len(p) + 1 <= max_chars:
            cur = (cur + " " + p).strip()
        else:
            if cur:
                chunks.append(cur)
            cur = p
    if cur:
        chunks.append(cur)
    return chunks or [text.strip()]


async def _speak(text: str, voice: str, out_path: str):
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(out_path)


def synthesize(text: str, voice: str, out_path: str,
               cancel_event=None) -> str:
    """
    Generate speech MP3 at out_path. Returns out_path.
    Raises VoiceoverError with a friendly message on failure.
    """
    text = (text or "").strip()
    if not text:
        raise VoiceoverError("There is no speech text for this clip.")
    chunks = _split_sentences(text)
    try:
        import edge_tts  # noqa: F401
    except ImportError as exc:
        raise VoiceoverError(
            "Voice engine is missing. Reinstall the app or run: "
            "pip install edge-tts") from exc
    import tempfile
    from pathlib import Path
    tmpdir = Path(tempfile.mkdtemp(prefix="aas_voice_"))
    try:
        async def _run():
            files = []
            for i, ch in enumerate(chunks):
                if cancel_event is not None and cancel_event.is_set():
                    raise VoiceoverError("Cancelled.")
                part = tmpdir / f"p{i:03d}.mp3"
                await _speak(ch, voice, str(part))
                files.append(part)
            # join parts with ffmpeg (already bundled)
            from core.media import get_ffmpeg_exe
            import subprocess
            lst = tmpdir / "list.txt"
            lst.write_text("".join(f"file '{f.as_posix()}'\n" for f in files),
                           encoding="utf-8")
            subprocess.run(
                [get_ffmpeg_exe(), "-y", "-v", "error", "-f", "concat",
                 "-safe", "0", "-i", str(lst), "-c", "copy", out_path],
                check=True, capture_output=True)
        asyncio.run(_run())
    except VoiceoverError:
        raise
    except Exception as exc:
        msg = str(exc).lower()
        if "connect" in msg or "network" in msg or "timeout" in msg:
            raise VoiceoverError(
                "Could not reach the voice service. "
                "Check your internet connection.") from exc
        raise VoiceoverError(f"Voiceover failed: {str(exc)[:140]}") from exc
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)
    return out_path


def preview_voice(voice: str, out_path: str) -> str:
    """Generate the short preview sample for a voice."""
    return synthesize(PREVIEW_TEXT, voice, out_path)
