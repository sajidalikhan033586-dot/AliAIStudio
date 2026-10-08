"""
Ali AI Studio - Free AI Clipper for Creators (Module 2)
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

        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("1020x680")
        self.minsize(900, 620)
        self.configure(fg_color=self.theme["bg"])

        ctk.set_appearance_mode("dark")

        self.current_frame = None
        if self.config.get("first_run", True):
            self.show_welcome()
        else:
            self.show_dashboard()

    def _switch(self, frame_cls):
        if self.current_frame is not None:
            self.current_frame.destroy()
        self.current_frame = frame_cls(self, self)
        self.current_frame.pack(fill="both", expand=True)

    def show_welcome(self):
        self._switch(WelcomeScreen)

    def show_keys(self):
        self._switch(KeysScreen)

    def show_dashboard(self):
        self._switch(DashboardScreen)

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
