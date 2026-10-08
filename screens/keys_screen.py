"""API key management screen (add / test / remove keys, usage meter)."""
import customtkinter as ctk
from core.keys import KeyManager


class KeysScreen(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=app.theme["bg"])
        self.app = app
        self.km = KeyManager(app.config)
        t = app.theme

        ctk.CTkLabel(self, text="Gemini API Keys", font=("Segoe UI", 26, "bold"),
                     text_color=t["text"]).pack(pady=(36, 4))
        ctk.CTkLabel(self, text="Smart Mode is optional. Keys stay on your PC.\nAdd more than one — the app switches automatically if a limit is reached.",
                     font=("Segoe UI", 13), text_color=t["text_dim"]).pack(pady=(0, 16))

        self.status = ctk.CTkLabel(self, text="", font=("Segoe UI", 13),
                                   text_color=t["text_dim"], wraplength=640)
        self.status.pack(pady=4)

        row = ctk.CTkFrame(self, fg_color=t["bg"])
        row.pack(pady=10)
        self.entry = ctk.CTkEntry(row, placeholder_text="Paste your Gemini API key here",
                                  width=400, height=44, font=("Segoe UI", 13),
                                  fg_color=t["panel"], text_color=t["text"],
                                  border_color=t["accent"])
        self.entry.pack(side="left", padx=(0, 10))
        ctk.CTkButton(row, text="Save & Test Key", height=44,
                      font=("Segoe UI", 13, "bold"),
                      fg_color=t["accent"], hover_color=t["accent_hover"],
                      text_color=t["button_text"],
                      command=self.save_key).pack(side="left")

        self.list_frame = ctk.CTkFrame(self, fg_color=t["bg"], width=560)
        self.list_frame.pack(pady=12)
        self.refresh_list()

        self.usage_label = ctk.CTkLabel(self, text=self.km.usage_text(),
                                        font=("Segoe UI", 12), text_color=t["text_dim"])
        self.usage_label.pack(pady=4)

        btn_row = ctk.CTkFrame(self, fg_color=t["bg"])
        btn_row.pack(pady=14)
        ctk.CTkButton(btn_row, text="← Back", width=130, height=42,
                      fg_color=t["panel"], hover_color="#1A2B47", text_color=t["text"],
                      command=self._go_back).pack(side="left", padx=8)
        ctk.CTkButton(btn_row, text="Continue →", width=200, height=42,
                      font=("Segoe UI", 14, "bold"),
                      fg_color=t["accent"], hover_color=t["accent_hover"],
                      text_color=t["button_text"],
                      command=app.finish_setup).pack(side="left", padx=8)

    def _go_back(self):
        # After setup, Back returns to the dashboard; on first run, to welcome.
        if self.app.config.get("first_run", True):
            self.app.show_welcome()
        else:
            self.app.show_dashboard()

    def save_key(self):
        key = self.entry.get().strip()
        t = self.app.theme
        self.status.configure(text="Testing key with Google...", text_color=t["text_dim"])
        self.update_idletasks()
        ok, msg = self.km.add_key(key)
        self.status.configure(text=msg,
                              text_color=t["success"] if ok else t["danger"])
        if ok:
            self.entry.delete(0, "end")
        self.refresh_list()

    def refresh_list(self):
        for w in self.list_frame.winfo_children():
            w.destroy()
        t = self.app.theme
        keys = self.km.masked_keys()
        if not keys:
            ctk.CTkLabel(self.list_frame, text="No keys added yet.",
                         text_color=t["text_dim"], font=("Segoe UI", 13)).pack()
            return
        for i, masked in enumerate(keys):
            row = ctk.CTkFrame(self.list_frame, fg_color=t["panel"])
            row.pack(pady=4, fill="x")
            ctk.CTkLabel(row, text=f"Key {i + 1}:   {masked}", font=("Consolas", 12),
                         text_color=t["text"]).pack(side="left", padx=14, pady=8)
            ctk.CTkButton(row, text="Remove", width=84, fg_color="transparent",
                          border_width=1, border_color=t["danger"],
                          text_color=t["danger"], hover_color="#2A1215",
                          command=lambda idx=i: self.remove_key(idx)).pack(side="right", padx=10)

    def remove_key(self, idx):
        self.km.remove_key(idx)
        self.refresh_list()
