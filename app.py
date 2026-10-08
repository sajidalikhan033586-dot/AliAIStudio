"""
Ali AI Studio - Free AI Clipper for Creators (Module 1)
Entry point. Shows the welcome screen on first run.
"""
import sys
import traceback
import customtkinter as ctk

from assets.theme import THEMES, APP_NAME, APP_VERSION
from core.config import load_config, save_config
from core.logger import setup_logger, show_error_dialog
from screens.welcome import WelcomeScreen
from screens.keys_screen import KeysScreen


class AliAIStudioApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.theme = THEMES[self.config.get("theme", "midnight_cyan")]

        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("900x620")
        self.minsize(800, 560)
        self.configure(fg_color=self.theme["bg"])

        ctk.set_appearance_mode("dark")

        self.current_frame = None
        if self.config.get("first_run", True):
            self.show_welcome()
        else:
            self.show_dashboard_placeholder()

    def _switch(self, frame_cls):
        if self.current_frame is not None:
            self.current_frame.destroy()
        self.current_frame = frame_cls(self, self)
        self.current_frame.pack(fill="both", expand=True)

    def show_welcome(self):
        self._switch(WelcomeScreen)

    def show_keys(self):
        self._switch(KeysScreen)

    def finish_setup(self):
        """Called when the user picks Free Mode or continues from the keys screen."""
        self.config["first_run"] = False
        save_config(self.config)
        self.show_dashboard_placeholder()

    def show_dashboard_placeholder(self):
        # Module 2 will build the real dashboard.
        if self.current_frame is not None:
            self.current_frame.destroy()
        frame = ctk.CTkFrame(self, fg_color=self.theme["bg"])
        frame.pack(fill="both", expand=True)
        ctk.CTkLabel(frame, text="Module 1 is working!",
                     font=("Segoe UI", 22, "bold"),
                     text_color=self.theme["text"]).pack(pady=(80, 10))
        ctk.CTkLabel(frame, text="Setup + welcome + API keys are done.\nThe dashboard will be built in Module 2.",
                     font=("Segoe UI", 14), text_color=self.theme["text_dim"]).pack()
        ctk.CTkButton(frame, text="Back to Welcome", width=180,
                      fg_color=self.theme["panel"], text_color=self.theme["text"],
                      command=self.show_welcome).pack(pady=30)
        self.current_frame = frame


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
