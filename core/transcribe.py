"""Offline speech-to-text with faster-whisper.

- 100% offline after the first run (model downloads once, then stays on PC).
- Default model "tiny" (~75MB, fastest - best for old laptops).
- Translation to English auto-switches to "base" (~150MB): tiny is too
  weak for speech->English translation.
- Returns word-level timestamps so captions can highlight word by word.
"""
import subprocess
import tempfile
from pathlib import Path

from core.media import get_ffmpeg_exe

MODEL_SIZES = ("tiny", "base")


class TranscribeError(Exception):
    """User-friendly transcription failure."""


def _check_cancel(cancel_event):
    if cancel_event is not None and cancel_event.is_set():
        raise TranscribeError("Cancelled.")


def extract_audio_wav(video_path: str, cancel_event=None) -> str:
    """Extract 16kHz mono WAV (what Whisper wants) to a temp file."""
    _check_cancel(cancel_event)
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    cmd = [get_ffmpeg_exe(), "-y", "-v", "error",
           "-i", video_path, "-vn", "-ac", "1", "-ar", "16000",
           "-c:a", "pcm_s16le", tmp.name]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as exc:
        raise TranscribeError(
            "Could not read the audio from this video. "
            "Try a different file (MP4 works best)."
        ) from exc
    _check_cancel(cancel_event)
    return tmp.name


class Transcriber:
    def __init__(self, app_dir: Path, model_size: str = "tiny",
                 status_cb=None, cancel_event=None):
        """
        status_cb: callable(text) for user-visible progress messages.
        cancel_event: threading.Event to abort between stages.
        """
        self.app_dir = Path(app_dir)
        self.model_size = model_size if model_size in MODEL_SIZES else "tiny"
        self.status_cb = status_cb or (lambda _t: None)
        self.cancel_event = cancel_event
        self._model = None

    def _say(self, text: str):
        try:
            self.status_cb(text)
        except Exception:
            pass

    def _load_model(self):
        if self._model is not None:
            return self._model
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise TranscribeError(
                "Speech engine is missing. Reinstall the app or run: "
                "pip install faster-whisper"
            ) from exc
        models_dir = self.app_dir / "models"
        models_dir.mkdir(parents=True, exist_ok=True)
        first_time = not any(models_dir.iterdir())
        if first_time:
            approx = "~75MB" if self.model_size == "tiny" else "~150MB"
            self._say(f"Downloading speech model ({approx}, one-time)...")
        else:
            self._say("Loading speech model...")
        try:
            # int8 on CPU: lightest mode, made for slow laptops.
            self._model = WhisperModel(
                self.model_size, device="cpu", compute_type="int8",
                download_root=str(models_dir),
            )
        except Exception as exc:
            msg = str(exc)
            if "proxy" in msg.lower() or "connect" in msg.lower() or "url" in msg.lower():
                raise TranscribeError(
                    "Could not download the speech model. "
                    "Check your internet connection and try again."
                ) from exc
            raise TranscribeError(f"Could not load the speech model: {msg[:160]}") from exc
        _check_cancel(self.cancel_event)
        return self._model

    def transcribe(self, video_path: str, translate_to_english: bool = False) -> dict:
        """
        Returns {"segments": [...], "language": "en", "duration": float}.
        Each segment: {"start","end","text","words":[{"word","start","end"}]}.
        Times are in seconds, relative to the full video.
        """
        wav = extract_audio_wav(video_path, self.cancel_event)
        try:
            # Translation (speech -> English) needs the bigger model.
            model_size = "base" if translate_to_english else self.model_size
            if translate_to_english and self.model_size != "base":
                self._say("English translation needs the accurate model - switching...")
                self.model_size = "base"
                self._model = None
            model = self._load_model()
            task = "translate" if translate_to_english else "transcribe"
            self._say("Transcribing speech to text... (this takes a few minutes)")
            try:
                segments, info = model.transcribe(
                    wav, task=task, word_timestamps=True, beam_size=1,
                )
            except Exception as exc:
                raise TranscribeError(
                    f"Transcription failed: {str(exc)[:160]}"
                ) from exc
            _check_cancel(self.cancel_event)
            out = []
            for seg in segments:
                words = []
                for w in (seg.words or []):
                    words.append({"word": w.word.strip(),
                                  "start": float(w.start), "end": float(w.end)})
                out.append({"start": float(seg.start), "end": float(seg.end),
                            "text": seg.text.strip(), "words": words})
            _check_cancel(self.cancel_event)
            self._say(f"Done - {len(out)} speech segments found.")
            return {"segments": out,
                    "language": getattr(info, "language", "en") or "en",
                    "duration": float(getattr(info, "duration", 0) or 0)}
        finally:
            try:
                Path(wav).unlink(missing_ok=True)
            except Exception:
                pass
