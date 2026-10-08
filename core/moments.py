"""Find viral moments in a transcript.

Two modes:
- FREE (default, offline): heuristic scoring on the transcript text.
- SMART (needs a Gemini API key): the transcript TEXT ONLY (never the video)
  is sent to Google; the model picks moments and explains them.

Smart Mode falls back to Free Mode automatically if the key fails, and the
app says so out loud (never a silent switch).

NO-SPEECH FALLBACK: if the video has little/no speech (music reels etc.),
the app finds the most ENERGETIC parts from the audio loudness instead -
so no video ever comes back empty.
"""
import json
import re
import subprocess
import urllib.request
import urllib.error

from core.media import get_ffmpeg_exe

GEMINI_URL = ("https://generativelanguage.googleapis.com/v1beta/models/"
              "gemini-2.0-flash:generateContent")

HOOK_WORDS = {
    "secret", "secrets", "free", "never", "always", "mistake", "mistakes",
    "truth", "lie", "lies", "best", "worst", "amazing", "incredible",
    "shocking", "stop", "warning", "hack", "hacks", "trick", "tricks",
    "how", "why", "what", "million", "billion", "guaranteed", "proven",
    "nobody", "everyone",
}


def _segment_score(seg) -> tuple:
    """Returns (score, reasons list) for one transcript segment."""
    text = seg["text"]
    words = text.split()
    score, reasons = 0.0, []
    if "?" in text:
        score += 2.0
        reasons.append("asks a question")
    if "!" in text:
        score += 2.0
        reasons.append("high energy moment")
    if re.search(r"\d", text):
        score += 1.5
        reasons.append("mentions numbers/stats")
    hooks = sorted({w.strip(".,!?\"'").lower() for w in words} & HOOK_WORDS)
    if hooks:
        score += min(2.0, 1.0 + 0.25 * len(hooks))
        reasons.append("hook words: " + ", ".join(hooks[:3]))
    n = len(words)
    if 6 <= n <= 30:
        score += 1.0
    elif n < 3:
        score -= 1.0
    if text and text[0].isupper() and text.rstrip().endswith((".", "?", "!")):
        score += 0.5  # complete sentence: clean cut point
    return score, reasons


def _snap_window(segments, start, end):
    """Snap window edges to the nearest segment boundaries."""
    s = min((g["start"] for g in segments if g["start"] >= start - 1.0),
            default=start)
    e = max((g["end"] for g in segments if g["end"] <= end + 1.0),
            default=end)
    return max(0.0, s), max(s + 5.0, e)


def find_moments_free(segments, n_clips=2, clip_len=60) -> list:
    """Heuristic moment detection. Pure offline."""
    if not segments:
        return []
    scored = [(seg, *_segment_score(seg)) for seg in segments]
    video_end = max(s["end"] for s in segments)
    candidates = []
    for seg, base, reasons in scored:
        start, end = _snap_window(segments, seg["start"], seg["start"] + clip_len)
        end = min(end, video_end)
        if end - start < 10:
            continue
        total, why = base, list(reasons)
        for s2, b2, r2 in scored:
            if s2 is not seg and s2["start"] >= start and s2["end"] <= end:
                total += b2 * 0.5
        # slight preference for earlier moments (hooks), but not only the start
        total += max(0.0, 1.0 - start / max(60.0, video_end)) * 0.5
        candidates.append({"start": round(start, 1), "end": round(end, 1),
                           "score": round(total, 1), "reasons": why})
    # greedy: best first, no heavy overlaps
    candidates.sort(key=lambda c: -c["score"])
    picked, out = [], []
    for c in candidates:
        if len(out) >= n_clips:
            break
        if any(not (c["end"] < p["start"] + 5 or c["start"] > p["end"] - 5)
               for p in picked):
            continue
        picked.append(c)
        text = " ".join(s["text"] for s in segments
                        if s["start"] >= c["start"] - 1 and s["end"] <= c["end"] + 1)
        words = text.split()
        c["title"] = " ".join(words[:7]) + ("..." if len(words) > 7 else "")
        c["reason"] = "; ".join(c["reasons"][:2]) or "strong segment"
        c["text"] = text
        del c["reasons"]
        out.append(c)
    out.sort(key=lambda c: c["start"])
    return out


def _transcript_text(segments, max_chars=12000) -> str:
    lines = []
    for s in segments:
        line = f"[{s['start']:.1f}-{s['end']:.1f}] {s['text']}"
        lines.append(line)
        if sum(len(l) for l in lines) > max_chars:
            break
    return "\n".join(lines)


def find_moments_smart(segments, n_clips, clip_len, key_manager,
                       status_cb=None) -> tuple:
    """
    Ask Gemini to pick moments. Returns (moments, notice).
    notice is a human message when falling back to Free Mode (never silent).
    Raises on programming errors only; API problems -> fallback.
    """
    say = status_cb or (lambda _t: None)
    transcript = _transcript_text(segments)
    prompt = (
        "You are a viral short-video editor. Below is a video transcript with "
        "timestamps [start-end in seconds]. Pick the "
        f"{n_clips} most viral-worthy moments. Each moment should be about "
        f"{clip_len} seconds long, with clean sentence boundaries.\n\n"
        "Reply with ONLY a JSON array, no other text. Each item:\n"
        '{"start": 12.5, "end": 72.5, "title": "short catchy title", '
        '"reason": "why this moment will go viral", "score": 8.5}\n\n'
        f"Transcript:\n{transcript}"
    )
    payload = json.dumps(
        {"contents": [{"parts": [{"text": prompt}]}],
         "generationConfig": {"temperature": 0.7}}).encode("utf-8")
    last_err = ""
    for _ in range(max(1, len(key_manager.masked_keys()))):
        key = key_manager.active_key()
        if not key:
            break
        say("Smart Mode: asking Gemini to find viral moments...")
        req = urllib.request.Request(
            f"{GEMINI_URL}?key={key}", data=payload,
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            key_manager.record_call()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            return _parse_smart(text, segments), ""
        except urllib.error.HTTPError as e:
            if e.code == 429:
                last_err = "API key limit reached"
                key_manager.rotate_key()
                continue
            if e.code in (400, 403):
                last_err = "API key invalid or expired"
                break
            last_err = f"Google error (HTTP {e.code})"
            break
        except Exception as exc:
            last_err = str(exc)[:120]
            break
    notice = (f"Smart Mode unavailable ({last_err}). "
              "Switched to Free Mode for this video.")
    return find_moments_free(segments, n_clips, clip_len), notice


def _parse_smart(text, segments) -> list:
    """Parse Gemini's JSON reply into moments; validate timestamps."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)
    items = json.loads(cleaned)
    video_end = max(s["end"] for s in segments) if segments else 0
    out = []
    for it in items:
        try:
            start = max(0.0, float(it["start"]))
            end = min(video_end, float(it["end"]))
        except (KeyError, TypeError, ValueError):
            continue
        if end - start < 5:
            continue
        words = " ".join(
            s["text"] for s in segments
            if s["end"] > start and s["start"] < end).split()
        out.append({
            "start": round(start, 1), "end": round(end, 1),
            "score": round(float(it.get("score", 7.0)), 1),
            "title": str(it.get("title", " ".join(words[:7])))[:80],
            "reason": str(it.get("reason", "picked by AI"))[:160],
            "text": " ".join(words),
        })
    return out


def find_moments(segments, n_clips=2, clip_len=60, smart=False,
                 key_manager=None, status_cb=None,
                 video_path=None, duration=0) -> tuple:
    """
    Returns (moments, notice). notice is "" normally, or a human message
    when Smart Mode fell back to Free Mode, or when the no-speech
    energy fallback was used.
    Chain: speech heuristics -> audio energy -> even time split.
    Never returns empty for a valid video.
    """
    total_speech = sum(s["end"] - s["start"] for s in segments)
    has_speech = len(segments) >= 3 and total_speech >= 15

    if has_speech:
        if smart and key_manager is not None and key_manager.has_keys():
            try:
                return find_moments_smart(segments, n_clips, clip_len,
                                          key_manager, status_cb)
            except Exception:
                pass  # fall through to Free Mode with notice below
            return (find_moments_free(segments, n_clips, clip_len),
                    "Smart Mode had a problem - used Free Mode instead.")
        return find_moments_free(segments, n_clips, clip_len), ""

    # ---- no clear speech: pick the most energetic parts ----
    say = status_cb or (lambda _t: None)
    say("No clear speech found - finding the most energetic parts...")
    dur = duration or (max((s["end"] for s in segments), default=0))
    moments = energy_moments(video_path, dur, n_clips, clip_len) if video_path else []
    if not moments and dur > 0:
        moments = time_split_moments(dur, n_clips, clip_len)
    notice = ("No clear speech in this video - picked the most energetic "
              "parts instead.")
    return moments, notice


# ================= no-speech fallbacks =================

def energy_curve(video_path: str, bin_sec: float = 2.0) -> list:
    """Loudness over time: [(bin_start_sec, avg_lufs), ...]. [] if unavailable."""
    try:
        exe = get_ffmpeg_exe()
        r = subprocess.run(
            [exe, "-hide_banner", "-nostats", "-i", video_path,
             "-map", "0:a", "-filter:a", "ebur128=framelog=info",
             "-f", "null", "-"],
            capture_output=True, text=True, timeout=300)
    except Exception:
        return []
    bins: dict = {}
    for line in (r.stderr or "").splitlines():
        m1 = re.search(r"t:\s*([\d.]+)", line)
        m2 = re.search(r"\bM:\s*(-?[\d.]+)", line)
        if not (m1 and m2):
            continue
        try:
            t, db = float(m1.group(1)), float(m2.group(1))
        except ValueError:
            continue
        if db < -70:  # silence
            continue
        bins.setdefault(int(t // bin_sec), []).append(db)
    return sorted((b * bin_sec, sum(v) / len(v)) for b, v in bins.items())


def _lufs_to_score(db: float) -> float:
    # momentary LUFS ~ -15 (loud) .. -45 (quiet) -> 1..10
    return round(max(1.0, min(10.0, 1.0 + (db + 50.0) / 4.0)), 1)


def energy_moments(video_path: str, duration: float,
                   n_clips: int = 2, clip_len: float = 60) -> list:
    """Pick highest-energy windows. Works for music/dance reels."""
    if not video_path or duration <= 0:
        return []
    clip_len = min(clip_len, duration)
    curve = energy_curve(video_path)
    if not curve:
        return time_split_moments(duration, n_clips, clip_len)
    bin_sec = 2.0
    win_bins = max(1, int(clip_len // bin_sec))
    cands = []
    for i in range(len(curve) - win_bins + 1):
        window = [db for _, db in curve[i:i + win_bins]]
        avg = sum(window) / len(window)
        cands.append((_lufs_to_score(avg), curve[i][0]))
    cands.sort(reverse=True)
    picked, out = [], []
    for score, s in cands:
        e = min(duration, s + clip_len)
        if e - s < 10:
            continue
        if any(not (e < p[0] + 5 or s > p[1] - 5) for p in picked):
            continue
        picked.append((s, e))
        out.append({"start": round(s, 1), "end": round(e, 1),
                    "score": score, "title": "Energetic moment",
                    "reason": "high energy part (music/beat)", "text": ""})
        if len(out) >= n_clips:
            break
    out.sort(key=lambda c: c["start"])
    return out or time_split_moments(duration, n_clips, clip_len)


def time_split_moments(duration: float, n_clips: int = 2,
                       clip_len: float = 60) -> list:
    """Last resort: split the video into even parts. Never empty."""
    if duration <= 0:
        return []
    clip_len = min(clip_len, duration)
    if duration < 10:
        return [{"start": 0.0, "end": round(duration, 1), "score": 5.0,
                 "title": "Full clip", "reason": "short video", "text": ""}]
    n = min(n_clips, max(1, int(duration // max(10.0, clip_len / 2))))
    part = duration / n
    out = []
    for i in range(n):
        s = round(i * part, 1)
        e = round(min(duration, s + clip_len), 1)
        if e - s < 5:
            continue
        out.append({"start": s, "end": e, "score": 5.0,
                    "title": f"Part {i + 1}", "reason": "even split",
                    "text": ""})
    return out
