"""Settings screen: transcription quality, defaults, updates, error log."""
import re
import threading
import urllib.request

import customtkinter as ctk

from assets.theme import APP_VERSION
from core.config import save_config
from core.logger import log_path_str

VERSION_URL = ("https://raw.githubusercontent.com/"
               "sajidalikhan033586-dot/AliAIStudio/main/assets/theme.py")


class SettingsScreen(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=app.theme["bg"])
        self.app = app
        self.t = app.theme
        self.cfg = app.config

        header = ctk.CTkFrame(self, fg_color=self.t["bg"])
        header.pack(fill="x", padx=20, pady=(12, 0))
        ctk.CTkButton(header, text="← Back", width=90, fg_color=self.t["panel"],
                      text_color=self.t["text"],
                      command=app.show_dashboard).pack(side="left")
        ctk.CTkLabel(header, text="Settings", font=("Segoe UI", 20, "bold"),
                     text_color=self.t["text"]).pack(side="left", padx=12)

        body = ctk.CTkFrame(self, fg_color=self.t["bg"])
        body.pack(fill="both", expand=True, padx=40, pady=20)

        # ---- transcription quality ----
        ctk.CTkLabel(body, text="Speech recognition quality",
                     font=("Segoe UI", 14, "bold"),
                     text_color=self.t["text"]).pack(anchor="w", pady=(6, 2))
        self.q_var = ctk.StringVar(
            value=self.cfg.get("transcribe_quality", "fast"))
        ctk.CTkRadioButton(body, text="Fast (recommended for old laptops)",
                           variable=self.q_var, value="fast",
                           fg_color=self.t["accent"],
                           text_color=self.t["text"]).pack(anchor="w", pady=2)
        ctk.CTkRadioButton(body, text="Accurate (slower, better for translation)",
                           variable=self.q_var, value="accurate",
                           fg_color=self.t["accent"],
                           text_color=self.t["text"]).pack(anchor="w", pady=2)

        # ---- caption language ----
        ctk.CTkLabel(body, text="Captions", font=("Segoe UI", 14, "bold"),
                     text_color=self.t["text"]).pack(anchor="w", pady=(14, 2))
        self.tr_var = ctk.BooleanVar(
            value=bool(self.cfg.get("translate_en", True)))
        ctk.CTkSwitch(body, text="Auto-translate captions to English",
                      variable=self.tr_var, fg_color=self.t["panel"],
                      progress_color=self.t["accent"],
                      text_color=self.t["text"]).pack(anchor="w", pady=2)

        # ---- default caption style ----
        from core.captions import PRESETS
        ctk.CTkLabel(body, text="Default caption style",
                     font=("Segoe UI", 14, "bold"),
                     text_color=self.t["text"]).pack(anchor="w", pady=(14, 2))
        cap_vals = [f"{k} - {v['label']}" for k, v in PRESETS.items()]
        cur = self.cfg.get("caption_preset", "tiktok")
        self.cap_var = ctk.StringVar(
            value=f"{cur} - {PRESETS.get(cur, PRESETS['tiktok'])['label']}")
        ctk.CTkOptionMenu(body, values=cap_vals, variable=self.cap_var,
                          fg_color=self.t["panel"],
                          button_color=self.t["accent"]).pack(anchor="w")

        # ---- buttons ----
        btns = ctk.CTkFrame(body, fg_color=self.t["bg"])
        btns.pack(fill="x", pady=(24, 0))
        ctk.CTkButton(btns, text="💾  Save", width=140,
                      fg_color=self.t["accent"],
                      text_color=self.t["button_text"],
                      command=self._save).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btns, text="🔄  Check for Updates", width=170,
                      fg_color=self.t["panel"], text_color=self.t["text"],
                      command=self._check_updates).pack(side="left", padx=8)
        ctk.CTkButton(btns, text="📄  Open Error Log", width=150,
                      fg_color=self.t["panel"], text_color=self.t["text"],
                      command=self._open_log).pack(side="left", padx=8)

        self.msg = ctk.CTkLabel(body, text="", font=("Segoe UI", 12),
                                text_color=self.t["text_dim"], wraplength=560,
                                justify="left")
        self.msg.pack(anchor="w", pady=(14, 0))
        ctk.CTkLabel(body, text=f"Ali AI Studio v{APP_VERSION}",
                     font=("Segoe UI", 11),
                     text_color=self.t["text_dim"]).pack(anchor="w", pady=(18, 0))

    def _ui(self, fn):
        try:
            self.after(0, fn)
        except Exception:
            pass

    def _save(self):
        self.cfg["transcribe_quality"] = self.q_var.get()
        self.cfg["translate_en"] = bool(self.tr_var.get())
        self.cfg["caption_preset"] = self.cap_var.get().split(" - ")[0]
        save_config(self.cfg)
        self.msg.configure(text="Settings saved.", text_color=self.t["text"])

    def _open_log(self):
        import os
        try:
            os.startfile(log_path_str())
        except Exception:
            self.msg.configure(text=f"Log file: {log_path_str()}",
                               text_color=self.t["text_dim"])

    def _check_updates(self):
        self.msg.configure(text="Checking for updates...",
                           text_color=self.t["text_dim"])
        threading.Thread(target=self._do_check, daemon=True).start()

    def _do_check(self):
        try:
            req = urllib.request.Request(VERSION_URL,
                                         headers={"User-Agent": "AliAIStudio"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                text = resp.read().decode("utf-8", "replace")
            m = re.search(r'APP_VERSION\s*=\s*"([\d.]+)"', text)
            if not m:
                raise ValueError("no version found")
            latest = m.group(1)
            if latest == APP_VERSION:
                msg = f"You have the latest version (v{APP_VERSION})."
            else:
                msg = (f"A new version is available: v{latest} "
                       f"(you have v{APP_VERSION}).\n"
                       f"Download it from your GitHub repo → Actions → "
                       f"latest build → Artifacts.")
            self._ui(lambda: self.msg.configure(text=msg,
                                                text_color=self.t["text"]))
        except Exception:
            self._ui(lambda: self.msg.configure(
                text="Could not check for updates. Check your internet.",
                text_color=self.t["danger"]))
