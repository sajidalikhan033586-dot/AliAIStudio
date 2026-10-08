"""Main dashboard: video input (file / YouTube / TikTok) + clip settings."""
import threading
import customtkinter as ctk
from pathlib import Path
from tkinter import filedialog
from PIL import Image

from core.config import save_config
from core.download import DownloadManager, DownloadCancelled, detect_source
from core.media import get_video_info, format_duration

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD  # noqa: F401
    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False


class DashboardScreen(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=app.theme["bg"])
        self.app = app
        self.t = app.theme
        self.cfg = app.config
        self.dm = DownloadManager(app.app_dir)
        self.video_path = None
        self.video_info = None
        self.cancel_event = threading.Event()

        # ---- header ----
        header = ctk.CTkFrame(self, fg_color=self.t["bg"])
        header.pack(fill="x", padx=20, pady=(12, 0))
        logo_path = Path(__file__).resolve().parent.parent / "assets" / "logo.png"
        if logo_path.exists():
            img = ctk.CTkImage(Image.open(logo_path), size=(34, 34))
            ctk.CTkLabel(header, image=img, text="").pack(side="left")
        ctk.CTkLabel(header, text="Ali AI Studio", font=("Segoe UI", 20, "bold"),
                     text_color=self.t["text"]).pack(side="left", padx=8)
        ctk.CTkButton(header, text="Keys", width=80, fg_color=self.t["panel"],
                      text_color=self.t["text"], command=app.show_keys).pack(side="right")

        steps = ctk.CTkLabel(self, text="Step 1: Add Video      →      Step 2: Generate Clips      →      Step 3: Export",
                             font=("Segoe UI", 12), text_color=self.t["text_dim"])
        steps.pack(pady=(2, 8))

        # ---- main columns ----
        main = ctk.CTkFrame(self, fg_color=self.t["bg"])
        main.pack(fill="both", expand=True, padx=20, pady=6)
        main.columnconfigure(0, weight=3)
        main.columnconfigure(1, weight=2)

        self._build_input_panel(main)
        self._build_settings_panel(main)

    # ================= input panel =================
    def _build_input_panel(self, main):
        t = self.t
        left = ctk.CTkFrame(main, fg_color=t["panel"], corner_radius=12)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        tabs = ctk.CTkTabview(left, fg_color=t["panel"],
                              segmented_button_fg_color=t["bg"],
                              segmented_button_selected_color=t["accent"],
                              segmented_button_selected_text_color=t["button_text"],
                              text_color=t["text"])
        tabs.pack(fill="x", padx=14, pady=12)
        for name in ("Computer", "YouTube", "TikTok"):
            tabs.add(name)
            tabs.tab(name).configure(fg_color=t["panel"])

        # --- Computer tab ---
        comp = tabs.tab("Computer")
        self.drop = ctk.CTkFrame(comp, fg_color=t["bg"], corner_radius=10,
                                 border_width=2, border_color=t["accent"])
        self.drop.pack(fill="x", padx=6, pady=8)
        hint = "Drop your video here\n(or click to browse)" if DND_AVAILABLE else "Click to browse your video"
        dl = ctk.CTkLabel(self.drop, text=hint, font=("Segoe UI", 14),
                          text_color=t["text_dim"], cursor="hand2")
        dl.pack(pady=26)
        dl.bind("<Button-1>", lambda e: self.browse_file())
        self.drop.bind("<Button-1>", lambda e: self.browse_file())
        if DND_AVAILABLE and getattr(self.app, "dnd_enabled", False):
            self.drop.drop_target_register(DND_FILES)
            self.drop.dnd_bind("<<Drop>>", self._on_drop)
        self.file_label = ctk.CTkLabel(comp, text="No file selected", font=("Segoe UI", 12),
                                       text_color=t["text_dim"], wraplength=320)
        self.file_label.pack(pady=(0, 10))

        # --- Link tabs ---
        for name in ("YouTube", "TikTok"):
            tab = tabs.tab(name)
            entry = ctk.CTkEntry(tab, placeholder_text=f"Paste {name} link here…",
                                 height=42, font=("Segoe UI", 13),
                                 fg_color=t["bg"], text_color=t["text"],
                                 border_color=t["accent"])
            entry.pack(fill="x", padx=6, pady=10)
            setattr(self, f"{name.lower()}_entry", entry)
            ctk.CTkButton(tab, text="Download", height=40, font=("Segoe UI", 13, "bold"),
                          fg_color=t["accent"], hover_color=t["accent_hover"],
                          text_color=t["button_text"],
                          command=lambda n=name: self.download_link(n)).pack(pady=(0, 10))

        # --- progress + status ---
        self.progress = ctk.CTkProgressBar(left, fg_color=t["bg"], progress_color=t["accent"])
        self.status = ctk.CTkLabel(left, text="", font=("Segoe UI", 12),
                                   text_color=t["text_dim"], wraplength=380)
        self.cancel_btn = ctk.CTkButton(left, text="Cancel", width=100,
                                        fg_color="transparent", border_width=1,
                                        border_color=t["danger"], text_color=t["danger"],
                                        command=self._cancel_download)

        # --- video info card ---
        self.info_card = ctk.CTkFrame(left, fg_color=t["bg"], corner_radius=10)
        self.info_title = ctk.CTkLabel(self.info_card, text="", font=("Segoe UI", 14, "bold"),
                                       text_color=t["text"], wraplength=360, justify="left")
        self.info_title.pack(anchor="w", padx=12, pady=(10, 2))
        self.info_sub = ctk.CTkLabel(self.info_card, text="", font=("Segoe UI", 12),
                                     text_color=t["text_dim"], wraplength=360, justify="left")
        self.info_sub.pack(anchor="w", padx=12, pady=(0, 10))

    # ================= settings panel =================
    def _build_settings_panel(self, main):
        t = self.t
        right = ctk.CTkFrame(main, fg_color=t["panel"], corner_radius=12)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        ctk.CTkLabel(right, text="Clip Settings", font=("Segoe UI", 18, "bold"),
                     text_color=t["text"]).pack(pady=(16, 10))

        # number of clips (default 2)
        self.clips_var = ctk.IntVar(value=int(self.cfg.get("clips_count", 2)))
        ctk.CTkLabel(right, text="Number of clips", font=("Segoe UI", 13),
                     text_color=t["text"]).pack(anchor="w", padx=18)
        self.clips_label = ctk.CTkLabel(right, text=f"{self.clips_var.get()} clips",
                                        font=("Segoe UI", 13, "bold"), text_color=t["accent"])
        self.clips_label.pack(anchor="e", padx=18)
        ctk.CTkSlider(right, from_=1, to=10, number_of_steps=9, variable=self.clips_var,
                      fg_color=t["bg"], progress_color=t["accent"],
                      button_color=t["accent"],
                      command=self._on_clips_change).pack(fill="x", padx=18, pady=(0, 12))

        # clip length (default 60s, max 3 min)
        self.len_var = ctk.IntVar(value=int(self.cfg.get("clip_length", 60)))
        ctk.CTkLabel(right, text="Clip length", font=("Segoe UI", 13),
                     text_color=t["text"]).pack(anchor="w", padx=18)
        self.len_label = ctk.CTkLabel(right, text=f"{self.len_var.get()}s",
                                      font=("Segoe UI", 13, "bold"), text_color=t["accent"])
        self.len_label.pack(anchor="e", padx=18)
        ctk.CTkSlider(right, from_=15, to=180, number_of_steps=165, variable=self.len_var,
                      fg_color=t["bg"], progress_color=t["accent"],
                      button_color=t["accent"],
                      command=self._on_len_change).pack(fill="x", padx=18, pady=(0, 12))

        # format
        ctk.CTkLabel(right, text="Format", font=("Segoe UI", 13),
                     text_color=t["text"]).pack(anchor="w", padx=18)
        self.fmt_var = ctk.StringVar(value=self.cfg.get("clip_format", "9:16"))
        seg = ctk.CTkSegmentedButton(right, values=["9:16", "16:9"], variable=self.fmt_var,
                                     fg_color=t["bg"], selected_color=t["accent"],
                                     selected_hover_color=t["accent_hover"],
                                     unselected_color=t["bg"], text_color=t["text"],
                                     command=self._on_fmt_change)
        seg.pack(fill="x", padx=18, pady=(0, 18))

        ctk.CTkButton(right, text="✨  Find Viral Clips", height=50,
                      font=("Segoe UI", 16, "bold"),
                      fg_color=t["accent"], hover_color=t["accent_hover"],
                      text_color=t["button_text"],
                      command=self._find_clips).pack(fill="x", padx=18, pady=(0, 18))

    # ================= actions =================
    def _on_clips_change(self, _):
        v = self.clips_var.get()
        self.clips_label.configure(text=f"{v} clips")
        self.cfg["clips_count"] = v
        save_config(self.cfg)

    def _on_len_change(self, _):
        v = self.len_var.get()
        self.len_label.configure(text=f"{v}s")
        self.cfg["clip_length"] = v
        save_config(self.cfg)

    def _on_fmt_change(self, _):
        self.cfg["clip_format"] = self.fmt_var.get()
        save_config(self.cfg)

    def _on_drop(self, event):
        path = event.data.strip().strip("{}")
        self._load_local(path)

    def browse_file(self):
        path = filedialog.askopenfilename(
            title="Choose a video",
            filetypes=[("Video files", "*.mp4 *.mov *.webm *.mkv *.avi *.m4v"),
                       ("All files", "*.*")])
        if path:
            self._load_local(path)

    def _load_local(self, path):
        res = self.dm.check_local_file(path)
        if not res["ok"]:
            self._set_status(res["message"], error=True)
            return
        self._show_info({"title": Path(path).stem, "path": path, "link": False})

    def download_link(self, platform):
        entry = getattr(self, f"{platform.lower()}_entry")
        url = entry.get().strip()
        if not url:
            self._set_status(f"Please paste a {platform} link first.", error=True)
            return
        if detect_source(url) == "unsupported":
            self._set_status("This does not look like a video link or file.", error=True)
            return
        self.cancel_event.clear()
        self._show_progress(True)
        self._set_status(f"Downloading from {platform}…")

        def progress_cb(done, total):
            pct = (done / total) if total else 0
            self.after(0, lambda: self.progress.set(min(max(pct, 0), 1)))

        def done_cb(result):
            self.after(0, lambda: self._download_done(result))

        self.dm.download_in_thread(url, progress_cb, done_cb, self.cancel_event)

    def _download_done(self, result):
        self._show_progress(False)
        if not result["ok"]:
            self._set_status(result["message"], error=True)
            return
        self._show_info({"title": Path(result["path"]).stem, "path": result["path"], "link": True})

    def _cancel_download(self):
        self.cancel_event.set()
        self._set_status("Cancelling…")

    def _show_info(self, basic):
        info = get_video_info(basic["path"])
        if not info["ok"]:
            self._set_status(info["message"], error=True)
            return
        self.video_path = basic["path"]
        self.video_info = info
        res = f"{info['width']}x{info['height']}" if info["width"] else "—"
        self.info_title.configure(text=info["title"][:60])
        self.info_sub.configure(
            text=f"Duration: {info['duration_text']}    •    Size: {info['size_mb']} MB    •    {res}")
        self.info_card.pack(fill="x", padx=14, pady=10)
        self._set_status("Video ready! Adjust settings and press Find Viral Clips.")

    def _find_clips(self):
        if not self.video_path:
            self._set_status("Add a video first (file or link).", error=True)
            return
        popup = ctk.CTkToplevel(self)
        popup.title("Coming next")
        popup.geometry("440x220")
        popup.configure(fg_color=self.t["bg"])
        popup.grab_set()
        ctk.CTkLabel(popup, text="Video is ready!",
                     font=("Segoe UI", 18, "bold"), text_color=self.t["text"]).pack(pady=(28, 6))
        ctk.CTkLabel(popup,
                     text=f"{self.video_info['duration_text']} video loaded.\n"
                          f"Settings: {self.clips_var.get()} clips × {self.len_var.get()}s, {self.fmt_var.get()}.\n\n"
                          "AI clipping (transcription + viral moments)\ncomes in Module 3.",
                     font=("Segoe UI", 13), text_color=self.t["text_dim"]).pack(pady=6)
        ctk.CTkButton(popup, text="OK", width=120, fg_color=self.t["accent"],
                      text_color=self.t["button_text"],
                      command=popup.destroy).pack(pady=10)

    # ================= helpers =================
    def _set_status(self, msg, error=False):
        color = self.t["danger"] if error else self.t["text_dim"]
        self.status.configure(text=msg, text_color=color)

    def _show_progress(self, show):
        if show:
            self.progress.set(0)
            self.progress.pack(fill="x", padx=14, pady=(4, 2))
            self.status.pack(pady=2)
            self.cancel_btn.pack(pady=4)
        else:
            self.progress.pack_forget()
            self.cancel_btn.pack_forget()
            self.status.pack(pady=6)
