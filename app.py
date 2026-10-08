"""
Ali AI Studio - Free AI Clipper for Creators (v0.3.0)
Entry point. Welcome screen on first run, dashboard afterwards.
"""
import sys
import traceback
import customtkinter as ctk

from assets.theme import THEMES, APP_NAME, APP_VERSION
from core.config import load_config, save_config, get_app_dir
from core.logger import setup_logger, show_error_dialog
from screens.welcome import WelcomeScreen
from screens.keys_screen import KeysScreen
from screens.dashboard import DashboardScreen, DND_AVAILABLE
from screens.analyze_screen import AnalyzeScreen
from screens.settings_screen import SettingsScreen

# Drag & drop is optional: if tkinterdnd2 is missing, click-to-browse still works.
if DND_AVAILABLE:
    from tkinterdnd2 import TkinterDnD
    _Base = (ctk.CTk, TkinterDnD.DnD2)
else:
    _Base = (ctk.CTk,)


class AliAIStudioApp(*_Base):
    def __init__(self):
        super().__init__()
        self.app_dir = get_app_dir()
        self.dnd_enabled = DND_AVAILABLE
        self.config = load_config()
        self.theme = THEMES[self.config.get("theme", "midnight_cyan")]
        # filled during analysis; used by the render pipeline for captions
        self.transcript = {"segments": [], "language": "en", "duration": 0}

        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("1020x700")
        self.minsize(900, 640)
        self.configure(fg_color=self.theme["bg"])

        ctk.set_appearance_mode("dark")

        self.current_frame = None
        if self.config.get("first_run", True):
            self.show_welcome()
        else:
            self.show_dashboard()

    def _switch(self, frame_cls, *args):
        if self.current_frame is not None:
            self.current_frame.destroy()
        self.current_frame = frame_cls(self, self, *args)
        self.current_frame.pack(fill="both", expand=True)

    def show_welcome(self):
        self._switch(WelcomeScreen)

    def show_keys(self):
        self._switch(KeysScreen)

    def show_dashboard(self):
        self._switch(DashboardScreen)

    def show_analyze(self, video_path: str):
        self._switch(AnalyzeScreen, video_path)

    def show_settings(self):
        self._switch(SettingsScreen)

    def finish_setup(self):
        """Called when the user picks Free Mode or continues from the keys screen."""
        self.config["first_run"] = False
        save_config(self.config)
        self.show_dashboard()


def main():
    setup_logger()
    try:
        app = AliAIStudioApp()
        app.mainloop()
    except Exception:
        details = traceback.format_exc()
        try:
            show_error_dialog(None, "Startup error", details)
        except Exception:
            print(details, file=sys.stderr)


if __name__ == "__main__":
    main()
