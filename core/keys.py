"""
Gemini API key management.

SECURITY (honest notes):
- Keys are stored OBFUSCATED on the user's own PC (not plain text).
  This is NOT encryption: anyone with access to the PC can decode it.
  It only protects against casual plain-text exposure.
- Keys are sent ONLY to Google's servers, and only when Smart Mode is used.
- config.json lives in %APPDATA% (outside the git repo), so keys can
  never leak through GitHub.

USAGE METER (honest notes):
- Google does not offer a live quota API, so the "remaining usage" shown
  in the app is the app's OWN count of calls it made today: an estimate,
  not an exact number.
- DAILY_SOFT_CAP is conservative on purpose (Google changes free limits).
"""
import base64
import datetime as dt
import json
import urllib.request
import urllib.error

GEMINI_TEST_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.0-flash:generateContent"
)
OBFUSCATION_PREFIX = "AAS1:"
DAILY_SOFT_CAP = 400  # conservative local estimate; Google publishes no fixed number


def obfuscate(key: str) -> str:
    raw = (OBFUSCATION_PREFIX + key.strip()).encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


def deobfuscate(stored: str) -> str:
    raw = base64.b64decode(stored.encode("ascii")).decode("utf-8")
    if raw.startswith(OBFUSCATION_PREFIX):
        raw = raw[len(OBFUSCATION_PREFIX):]
    return raw


def mask_key(key: str) -> str:
    key = key.strip()
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}...{key[-4:]}"


def test_key(key: str, timeout: int = 15):
    """
    Send a tiny test request to Google to check the key.
    Returns (ok: bool, message: str) with a user-friendly message.
    Uses only the standard library (no extra dependency).
    """
    key = key.strip()
    if not key:
        return False, "Key is empty. Please paste your Gemini API key."
    payload = json.dumps(
        {"contents": [{"parts": [{"text": "Reply with: OK"}]}]}
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{GEMINI_TEST_URL}?key={key}",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                return True, "Key is working! Smart Mode is ready."
            return False, f"Unexpected response from Google (HTTP {resp.status})."
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", "replace")
        except Exception:
            body = ""
        if e.code == 400:
            return False, "Invalid API key. Please check and paste it again."
        if e.code == 403:
            return False, "Key is blocked or expired. Please create a new key in Google AI Studio."
        if e.code == 429:
            return False, ("API key limit reached for today. "
                           "The app will use Free Mode until the limit resets.")
        return False, f"Google returned an error (HTTP {e.code}). Details: {body[:200]}"
    except urllib.error.URLError:
        return False, "No internet connection. Check your internet or continue in Free Mode."
    except Exception as exc:  # reported, never crashes
        return False, f"Could not test the key: {exc}"


class KeyManager:
    """Holds the user's keys in memory; persists obfuscated copies via config."""

    def __init__(self, config: dict):
        self.config = config
        self._keys = [deobfuscate(k) for k in config.get("keys", [])]

    def _persist(self):
        from core.config import save_config  # local import avoids cycles
        self.config["keys"] = [obfuscate(k) for k in self._keys]
        save_config(self.config)

    def add_key(self, key: str):
        ok, msg = test_key(key)
        if ok:
            key = key.strip()
            if key not in self._keys:
                self._keys.append(key)
                self._persist()
            return True, msg
        return False, msg

    def remove_key(self, index: int):
        if 0 <= index < len(self._keys):
            del self._keys[index]
            self._persist()

    def masked_keys(self):
        return [mask_key(k) for k in self._keys]

    def has_keys(self) -> bool:
        return len(self._keys) > 0

    def active_key(self):
        if not self._keys:
            return None
        idx = self.config.get("active_key_index", 0) % len(self._keys)
        return self._keys[idx]

    def rotate_key(self):
        """Switch to the next key (used when one hits its limit)."""
        if len(self._keys) > 1:
            idx = (self.config.get("active_key_index", 0) + 1) % len(self._keys)
            self.config["active_key_index"] = idx
            from core.config import save_config
            save_config(self.config)

    # ---- local daily usage estimate ----
    def _today(self) -> str:
        return dt.date.today().isoformat()

    def record_call(self):
        usage = self.config.setdefault("usage", {"date": "", "calls": 0})
        if usage.get("date") != self._today():
            usage["date"] = self._today()
            usage["calls"] = 0
        usage["calls"] += 1
        from core.config import save_config
        save_config(self.config)

    def usage_today(self) -> int:
        usage = self.config.get("usage", {"date": "", "calls": 0})
        if usage.get("date") != self._today():
            return 0
        return int(usage.get("calls", 0))

    def usage_text(self) -> str:
        return f"Today: ~{self.usage_today()} / {DAILY_SOFT_CAP} calls (estimate)"
