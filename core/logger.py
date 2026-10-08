"""
Error logging for Ali AI Studio.

- Every error is written to error_log.txt on the USER'S OWN PC
  (Windows: %APPDATA%/AliAIStudio/error_log.txt).
- NOTHING is ever sent anywhere automatically. To report a problem the
  user presses "Copy error details" and pastes it to support.
"""
import logging
import platform
import sys
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path

from assets.theme import APP_VERSION, THEMES


def _log_path() -> Path:
    from core.config import get_app_dir
    return get_app_dir() / "error_log.txt"


def log_path_str() -> str:
    return str(_log_path())


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("ali_ai_studio")
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        handler = RotatingFileHandler(
            _log_path(), maxBytes=200 * 1024, backupCount=2, encoding="utf-8"
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        )
        logger.addHandler(handler)
    sys.excepthook = _global_excepthook
    return logger


def _global_excepthook(exc_type, exc_value, exc_tb):
    details = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    logging.getLogger("ali_ai_studio").error("Unhandled error:\n%s", details)
    try:
        show_error_dialog(None, "Something went wrong", details)
    except Exception:
        print(details, file=sys.stderr)


def get_error_report(details: str) -> str:
    return (
        f"Ali AI Studio v{APP_VERSION} error report\n"
        f"System: {platform.system()} {platform.release()} ({platform.machine()})\n"
        f"Python: {platform.python_version()}\n"
        f"--- details ---\n{details}\n"
        f"--- end ---\n"
        f"(Full log: {log_path_str()})\n"
    )


def show_error_dialog(parent, title: str, details: str):
    """Popup with the error in simple words + a 'Copy error details' button."""
    import customtkinter as ctk
    theme = THEMES["midnight_cyan"]

    own_root = False
    if parent is None:
        parent = ctk.CTk()
        parent.withdraw()
        own_root = True

    dialog = ctk.CTkToplevel(parent)
    dialog.title("Ali AI Studio - Error")
    dialog.geometry("560x400")
    dialog.configure(fg_color=theme["bg"])
    dialog.grab_set()

    ctk.CTkLabel(dialog, text=title, font=("Segoe UI", 18, "bold"),
                 text_color=theme["text"]).pack(pady=(20, 5))
    ctk.CTkLabel(
        dialog,
        text="The error was saved to error_log.txt.\nCopy the details and send them to support.",
        font=("Segoe UI", 13), text_color=theme["text_dim"],
    ).pack(pady=5)

    box = ctk.CTkTextbox(dialog, font=("Consolas", 11), fg_color=theme["panel"],
                         text_color=theme["text"])
    box.pack(fill="both", expand=True, padx=20, pady=10)
    box.insert("1.0", details[-3000:])
    box.configure(state="disabled")

    def copy_details():
        dialog.clipboard_clear()
        dialog.clipboard_append(get_error_report(details))
        copy_btn.configure(text="Copied! Now paste it to support.")

    copy_btn = ctk.CTkButton(dialog, text="Copy error details", command=copy_details,
                             fg_color=theme["accent"], text_color=theme["button_text"],
                             font=("Segoe UI", 13, "bold"))
    copy_btn.pack(pady=(0, 8))
    ctk.CTkLabel(dialog, text=f"Log file: {log_path_str()}",
                 font=("Segoe UI", 10), text_color=theme["text_dim"]).pack(pady=(0, 16))

    if own_root:
        dialog.wait_window()
        parent.destroy()
