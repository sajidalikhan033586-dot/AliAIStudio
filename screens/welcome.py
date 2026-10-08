"""First-run welcome screen."""
import customtkinter as ctk
from pathlib import Path
from PIL import Image


class WelcomeScreen(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=app.theme["bg"])
        self.app = app
        t = app.theme

        # Logo (PNG preferred, WebP fallback)
        assets = Path(__file__).resolve().parent.parent / "assets"
        logo_path = assets / "logo.png"
        if not logo_path.exists():
            logo_path = assets / "logo.webp"
        if logo_path.exists():
            img = ctk.CTkImage(Image.open(logo_path), size=(110, 110))
            ctk.CTkLabel(self, image=img, text="").pack(pady=(46, 8))

        ctk.CTkLabel(self, text="Ali AI Studio", font=("Segoe UI", 38, "bold"),
                     text_color=t["text"]).pack()
        ctk.CTkLabel(self, text="Free AI Clipper for Creators", font=("Segoe UI", 16),
                     text_color=t["text_dim"]).pack(pady=(0, 28))

        ctk.CTkButton(self, text="Continue in Free Mode",
                      font=("Segoe UI", 16, "bold"),
                      fg_color=t["accent"], hover_color=t["accent_hover"],
                      text_color=t["button_text"],
                      width=320, height=52,
                      command=app.finish_setup).pack(pady=8)

        ctk.CTkButton(self, text="Add Gemini API Key (Smart Mode)",
                      font=("Segoe UI", 16),
                      fg_color=t["panel"], hover_color="#1A2B47",
                      text_color=t["accent"], border_width=2, border_color=t["accent"],
                      width=320, height=52,
                      command=app.show_keys).pack(pady=8)

        guide = ctk.CTkLabel(self, text="How to get a free key  →",
                             font=("Segoe UI", 13, "underline"),
                             text_color=t["accent"], cursor="hand2")
        guide.pack(pady=12)
        guide.bind("<Button-1>", lambda e: self.show_guide())

        ctk.CTkLabel(self, text="v0.1.0   •   100% free   •   Your videos never leave your PC",
                     font=("Segoe UI", 11), text_color=t["text_dim"]).pack(side="bottom", pady=18)

    def show_guide(self):
        t = self.app.theme
        popup = ctk.CTkToplevel(self)
        popup.title("Get a free Gemini API key")
        popup.geometry("580x450")
        popup.configure(fg_color=t["bg"])
        popup.grab_set()
        steps = (
            "How to get a FREE Gemini API key:\n\n"
            "1. Go to  aistudio.google.com\n"
            "2. Sign in with your Google account\n"
            "3. Click 'Get API Key' (top left)\n"
            "4. Click 'Create API key'\n"
            "5. Copy the key and paste it in this app\n\n"
            "The key is free. It stays on YOUR computer only.\n"
            "The app sends only text (never your videos) to Google."
        )
        ctk.CTkLabel(popup, text=steps, font=("Segoe UI", 14),
                     text_color=t["text"], justify="left").pack(padx=30, pady=28)
        ctk.CTkButton(popup, text="Got it", width=140,
                      fg_color=t["accent"], text_color=t["button_text"],
                      font=("Segoe UI", 13, "bold"),
                      command=popup.destroy).pack(pady=8)
