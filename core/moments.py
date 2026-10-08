"""Find viral moments in a transcript.

Two modes:
- FREE (default, offline): heuristic scoring on the transcript text.
- SMART (needs a Gemini API key): the transcript TEXT ONLY (never the video)
  is sent to Google; the model picks moments and explains them.

Smart Mode falls back to Free Mode automatically if the key fails, and the
app says so out loud (never a silent switch).
"""
import json
import re
import urllib.request
import urllib.error

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
                 key_manager=None, status_cb=None) -> tuple:
    """
    Returns (moments, notice). notice is "" normally, or a human message
    when Smart Mode fell back to Free Mode.
    """
    if smart and key_manager is not None and key_manager.has_keys():
        try:
            return find_moments_smart(segments, n_clips, clip_len,
                                      key_manager, status_cb)
        except Exception:
            pass  # fall through to Free Mode with notice below
        return (find_moments_free(segments, n_clips, clip_len),
                "Smart Mode had a problem - used Free Mode instead.")
    return find_moments_free(segments, n_clips, clip_len), ""
