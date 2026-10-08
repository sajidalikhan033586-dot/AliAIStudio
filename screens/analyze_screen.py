"""Analyze screen: transcribe -> viral moments -> generate clips.

Flow:
  1. Worker thread transcribes the video (offline faster-whisper).
  2. Moments are found (Free heuristics, or Smart Mode via Gemini key).
  3. User reviews/selects moments, picks captions + voiceover options.
  4. "Generate Clips" renders everything with a progress bar.
"""
import os
import threading
from pathlib import Path

import customtkinter as ctk
from PIL import Image

from core.config import save_config
from core.keys import KeyManager
from core.moments import find_moments
from core.pipeline import run_pipeline
from core.transcribe import Transcriber, TranscribeError
from core.voiceover import VOICES, voice_id_to_label, preview_voice


def _fmt_ts(sec: float) -> str:
    sec = max(0, int(sec))
    return f"{sec // 60}:{sec % 60:02d}"


class AnalyzeScreen(ctk.CTkFrame):
    def __init__(self, parent, app, video_path: str):
        super().__init__(parent, fg_color=app.theme["bg"])
        self.app = app
        self.t = app.theme
        self.cfg = app.config
        self.video_path = video_path
        self.cancel_event = threading.Event()
        self.moments = []
        self.out_files = []
        self._building = True

        # ---- header ----
        header = ctk.CTkFrame(self, fg_color=self.t["bg"])
        header.pack(fill="x", padx=20, pady=(12, 0))
        ctk.CTkButton(header, text="← Back", width=90, fg_color=self.t["panel"],
                      text_color=self.t["text"],
                      command=self._on_back).pack(side="left")
        ctk.CTkLabel(header, text="Find Viral Moments",
                     font=("Segoe UI", 20, "bold"),
                     text_color=self.t["text"]).pack(side="left", padx=12)
        self.mode_badge = ctk.CTkLabel(header, text="", font=("Segoe UI", 12),
                                       text_color=self.t["accent"])
        self.mode_badge.pack(side="right")

        sub = ctk.CTkLabel(self, text=Path(video_path).name,
                           font=("Segoe UI", 12), text_color=self.t["text_dim"])
        sub.pack(pady=(2, 6))

        # ---- stage 1: working ----
        self.work_frame = ctk.CTkFrame(self, fg_color=self.t["bg"])
        self.work_frame.pack(fill="both", expand=True, padx=40, pady=20)
        self.work_label = ctk.CTkLabel(
            self.work_frame, text="Preparing...", font=("Segoe UI", 15),
            text_color=self.t["text"])
        self.work_label.pack(pady=(60, 12))
        self.work_bar = ctk.CTkProgressBar(
            self.work_frame, fg_color=self.t["panel"],
            progress_color=self.t["accent"], width=420)
        self.work_bar.pack(pady=6)
        self.work_bar.start()
        self.work_status = ctk.CTkLabel(
            self.work_frame, text="", font=("Segoe UI", 12),
            text_color=self.t["text_dim"], wraplength=520)
        self.work_status.pack(pady=6)
        ctk.CTkButton(self.work_frame, text="Cancel", width=120,
                      fg_color="transparent", border_width=1,
                      border_color=self.t["danger"], text_color=self.t["danger"],
                      command=self._on_back).pack(pady=18)

        # ---- stage 2: results (hidden first) ----
        self.result_frame = ctk.CTkFrame(self, fg_color=self.t["bg"])

        threading.Thread(target=self._analyze, daemon=True).start()

    # ================= helpers =================
    def _ui(self, fn):
        try:
            self.after(0, fn)
        except Exception:
            pass

    def _on_back(self):
        self.cancel_event.set()
        self._building = False
        self.app.show_dashboard()

    # ================= stage 1: analyze =================
    def _say(self, text):
        self._ui(lambda: self.work_status.configure(text=text))

    def _analyze(self):
        try:
            km = KeyManager(self.cfg)
            smart = km.has_keys()
            self._ui(lambda: self.mode_badge.configure(
                text="✨ Smart Mode" if smart else "Free Mode"))

            quality = self.cfg.get("transcribe_quality", "fast")
            model_size = "base" if quality == "accurate" else "tiny"
            translate = bool(self.cfg.get("translate_en", True))

            tr = Transcriber(self.app.app_dir, model_size,
                             status_cb=self._say,
                             cancel_event=self.cancel_event)
            result = tr.transcribe(self.video_path,
                                   translate_to_english=translate)
            if self.cancel_event.is_set():
                return
            self.app.transcript = result

            n = int(self.cfg.get("clips_count", 2))
            length = int(self.cfg.get("clip_length", 60))
            moments, notice = find_moments(
                result["segments"], n_clips=n, clip_len=length,
                smart=smart, key_manager=km, status_cb=self._say)
            if self.cancel_event.is_set():
                return
            self.moments = moments
            self._ui(lambda: self._show_results(notice))
        except TranscribeError as exc:
            self._ui(lambda: self._show_error(str(exc)))
        except Exception as exc:
            self._ui(lambda: self._show_error(
                "Something went wrong. Details saved to error_log.txt."))

    def _show_error(self, msg):
        self.work_bar.stop()
        self.work_label.configure(text="Could not analyze this video",
                                  text_color=self.t["danger"])
        self.work_status.configure(text=msg)

    # ================= stage 2: review =================
    def _show_results(self, notice):
        self.work_frame.pack_forget()
        self._building = False
        rf = self.result_frame
        rf.pack(fill="both", expand=True, padx=20, pady=8)

        if notice:
            ctk.CTkLabel(rf, text=notice, font=("Segoe UI", 12),
                         text_color=self.t["warning"] if "warning" in self.t else "#FFB020",
                         wraplength=760, justify="left").pack(pady=(0, 6))

        if not self.moments:
            ctk.CTkLabel(rf, text="No strong moments found in this video.\n"
                                  "Try a video with more speech.",
                         font=("Segoe UI", 14),
                         text_color=self.t["text_dim"]).pack(pady=40)
            return

        ctk.CTkLabel(rf, text=f"{len(self.moments)} viral moments found - "
                              "uncheck any you don't want:",
                     font=("Segoe UI", 14, "bold"),
                     text_color=self.t["text"]).pack(pady=(0, 8))

        scroll = ctk.CTkScrollableFrame(rf, fg_color=self.t["panel"],
                                        height=260)
        scroll.pack(fill="both", expand=True, padx=4, pady=4)
        self.moment_vars = []
        for i, m in enumerate(self.moments):
            row = ctk.CTkFrame(scroll, fg_color=self.t["bg"], corner_radius=8)
            row.pack(fill="x", padx=6, pady=4)
            var = ctk.BooleanVar(value=True)
            self.moment_vars.append(var)
            ctk.CTkCheckBox(row, text="", variable=var, width=24,
                            fg_color=self.t["accent"]).pack(side="left", padx=8)
            info = (f"Clip {i+1}  •  {_fmt_ts(m['start'])} → {_fmt_ts(m['end'])}"
                    f"  •  Score {m['score']}/10\n"
                    f"{m['title']}\nWhy: {m['reason']}")
            ctk.CTkLabel(row, text=info, font=("Segoe UI", 12),
                         text_color=self.t["text"], justify="left",
                         anchor="w").pack(side="left", padx=4, pady=8)

        # ---- options ----
        opts = ctk.CTkFrame(rf, fg_color=self.t["bg"])
        opts.pack(fill="x", pady=(10, 4))
        opts.columnconfigure((0, 1, 2, 3), weight=1)

        ctk.CTkLabel(opts, text="Captions:", font=("Segoe UI", 12),
                     text_color=self.t["text_dim"]).grid(row=0, column=0)
        from core.captions import PRESETS
        cap_vals = [f"{k} - {v['label']}" for k, v in PRESETS.items()]
        self.cap_var = ctk.StringVar(
            value=f"{self.cfg.get('caption_preset', 'tiktok')} - "
                  f"{PRESETS[self.cfg.get('caption_preset', 'tiktok')]['label']}")
        ctk.CTkOptionMenu(opts, values=cap_vals, variable=self.cap_var,
                          fg_color=self.t["panel"],
                          button_color=self.t["accent"]).grid(row=1, column=0,
                                                             padx=6)

        ctk.CTkLabel(opts, text="AI Voiceover:", font=("Segoe UI", 12),
                     text_color=self.t["text_dim"]).grid(row=0, column=1)
        voice_vals = ["Off"] + [label for _, label in VOICES]
        saved_voice = self.cfg.get("voiceover_voice") or "Off"
        self.voice_var = ctk.StringVar(
            value=saved_voice if saved_voice in voice_vals else "Off")
        ctk.CTkOptionMenu(opts, values=voice_vals, variable=self.voice_var,
                          fg_color=self.t["panel"],
                          button_color=self.t["accent"],
                          command=self._on_voice_change).grid(row=1, column=1,
                                                             padx=6)
        self.preview_btn = ctk.CTkButton(opts, text="Preview voice",
                                         width=110, fg_color=self.t["panel"],
                                         text_color=self.t["text"],
                                         command=self._preview_voice,
                                         state="disabled")
        self.preview_btn.grid(row=2, column=1, pady=4)

        ctk.CTkLabel(opts, text="Audio:", font=("Segoe UI", 12),
                     text_color=self.t["text_dim"]).grid(row=0, column=2)
        self.audio_var = ctk.StringVar(value="Keep original")
        ctk.CTkOptionMenu(opts, values=["Keep original", "Duck under voice",
                                        "Replace with voice"],
                          variable=self.audio_var,
                          fg_color=self.t["panel"],
                          button_color=self.t["accent"]).grid(row=1, column=2,
                                                             padx=6)

        # ---- generate ----
        self.gen_btn = ctk.CTkButton(rf, text="⚡  Generate Clips", height=48,
                                     font=("Segoe UI", 16, "bold"),
                                     fg_color=self.t["accent"],
                                     hover_color=self.t["accent_hover"],
                                     text_color=self.t["button_text"],
                                     command=self._generate)
        self.gen_btn.pack(fill="x", padx=4, pady=(10, 4))
        self.gen_bar = ctk.CTkProgressBar(rf, fg_color=self.t["panel"],
                                          progress_color=self.t["accent"])
        self.gen_status = ctk.CTkLabel(rf, text="", font=("Segoe UI", 12),
                                       text_color=self.t["text_dim"])
        self.dl_frame = ctk.CTkFrame(rf, fg_color=self.t["bg"])

    def _on_voice_change(self, _val):
        self.preview_btn.configure(
            state="normal" if self.voice_var.get() != "Off" else "disabled")

    def _preview_voice(self):
        label = self.voice_var.get()
        vid = next((v for v, l in VOICES if l == label), VOICES[0][0])
        self.preview_btn.configure(state="disabled", text="Making...")
        def _work():
            try:
                import tempfile
                out = str(Path(tempfile.gettempdir()) / "aas_voice_preview.mp3")
                preview_voice(vid, out)
                os.startfile(out)  # opens in default media player
            except Exception as exc:
                self._ui(lambda: self.gen_status.configure(
                    text=f"Preview failed: {exc}", text_color=self.t["danger"]))
            finally:
                self._ui(lambda: self.preview_btn.configure(
                    state="normal", text="Preview voice"))
        threading.Thread(target=_work, daemon=True).start()

    # ================= stage 3: generate =================
    def _generate(self):
        picked = [m for m, v in zip(self.moments, self.moment_vars) if v.get()]
        if not picked:
            self.gen_status.configure(text="Select at least one clip.",
                                      text_color=self.t["danger"])
            return
        label = self.voice_var.get()
        voice = None if label == "Off" else next(
            (v for v, l in VOICES if l == label), None)
        audio_map = {"Keep original": "keep", "Duck under voice": "duck",
                     "Replace with voice": "replace"}
        audio_mode = audio_map[self.audio_var.get()]
        if voice is None:
            audio_mode = "keep"
        preset = self.cap_var.get().split(" - ")[0]
        self.cfg["caption_preset"] = preset
        self.cfg["voiceover_voice"] = label
        save_config(self.cfg)

        options = {"captions": True, "caption_preset": preset,
                   "voiceover": voice, "audio_mode": audio_mode,
                   "fmt": self.cfg.get("clip_format", "9:16")}
        # re-translate if the switch changed since analysis
        self.gen_btn.configure(state="disabled", text="Working...")
        self.gen_bar.pack(fill="x", padx=4, pady=6)
        self.gen_bar.set(0)
        self.gen_status.pack(pady=4)
        self._gen_cancel = threading.Event()

        def _pc(frac):
            self._ui(lambda: self.gen_bar.set(max(0.0, min(1.0, frac))))

        def _sc(text):
            self._ui(lambda: self.gen_status.configure(text=text))

        def _done(ok, msg, files):
            self.out_files = files
            self._ui(lambda: self._generate_done(ok, msg))

        run_pipeline(self.app, self.video_path, picked, options,
                     _pc, _sc, _done, self._gen_cancel)

    def _generate_done(self, ok, msg):
        self.gen_btn.configure(state="normal", text="⚡  Generate Clips")
        color = self.t["text"] if ok else self.t["danger"]
        self.gen_status.configure(text=msg, text_color=color)
        for w in self.dl_frame.winfo_children():
            w.destroy()
        if ok and self.out_files:
            self.dl_frame.pack(fill="x", pady=8)
            folder = str(Path(self.out_files[0]).parent)
            ctk.CTkButton(self.dl_frame, text="📂  Open Clips Folder",
                          fg_color=self.t["accent"],
                          text_color=self.t["button_text"],
                          command=lambda: os.startfile(folder)).pack(
                              side="left", padx=4)
            ctk.CTkButton(self.dl_frame, text="← Back to Dashboard",
                          fg_color=self.t["panel"], text_color=self.t["text"],
                          command=self._on_back).pack(side="left", padx=4)
