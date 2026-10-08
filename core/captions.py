"""Karaoke-style captions as ASS subtitles.

Word-level timings from faster-whisper become \\k karaoke tags, so each
word lights up exactly when it is spoken. Three presets, burned into the
video with ffmpeg's libass filter (no extra installs).
"""
import re

# ASS colors are &HAABBGGRR (AA=transparency, then Blue Green Red).
PRESETS = {
    "tiktok": {
        "label": "TikTok Pop",
        "font": "Arial", "size": 88, "bold": True,
        "base": "&H00FFFFFF",      # white
        "highlight": "&H0000D7FF",  # warm yellow
        "outline": "&H00000000", "outline_w": 3, "shadow": 1,
    },
    "neon": {
        "label": "Neon Glow",
        "font": "Arial", "size": 84, "bold": True,
        "base": "&H00E0E0E0",
        "highlight": "&H0000FFFF",  # cyan
        "outline": "&H80000000", "outline_w": 2, "shadow": 2,
    },
    "minimal": {
        "label": "Clean Minimal",
        "font": "Arial", "size": 64, "bold": False,
        "base": "&H00FFFFFF",
        "highlight": "&H00FFFFFF",
        "outline": "&H99000000", "outline_w": 2, "shadow": 0,
    },
}

MAX_WORDS_PER_LINE = 5


def _fmt_time(sec: float) -> str:
    sec = max(0.0, sec)
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    cs = int(round((sec - int(sec)) * 100))
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _clean(text: str) -> str:
    # ASS special chars: escape braces, strip newlines.
    return re.sub(r"[\r\n]+", " ", text).replace("{", "(").replace("}", ")")


def build_ass(segments: list, clip_start: float, clip_end: float,
              preset: str = "tiktok") -> str:
    """
    Build an ASS subtitle string for words inside [clip_start, clip_end).
    Times are re-based so the clip starts at 0.
    """
    p = PRESETS.get(preset, PRESETS["tiktok"])
    words = []
    for seg in segments:
        for w in seg.get("words", []):
            if w["end"] > clip_start and w["start"] < clip_end:
                words.append(w)
    # group into short lines
    lines, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= MAX_WORDS_PER_LINE:
            lines.append(cur)
            cur = []
    if cur:
        lines.append(cur)

    bold = "-1" if p["bold"] else "0"
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{p["font"]},{p["size"]},{p["highlight"]},{p["base"]},{p["outline"]},&H00000000,{bold},0,0,0,100,100,0,0,1,{p["outline_w"]},{p["shadow"]},2,40,40,120,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    for line in lines:
        t0 = max(0.0, line[0]["start"] - clip_start)
        t1 = max(t0 + 0.3, line[-1]["end"] - clip_start)
        parts = []
        for w in line:
            dur_cs = max(1, int(round((w["end"] - w["start"]) * 100)))
            parts.append(f"{{\\k{dur_cs}}}{_clean(w['word'])}")
        events.append(
            f"Dialogue: 0,{_fmt_time(t0)},{_fmt_time(t1)},Cap,,0,0,0,,"
            + " ".join(parts))
    return header + "\n".join(events) + "\n"
