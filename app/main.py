"""
main.py — Application entry point.
Initialises CustomTkinter, launches the main window, and starts the event loop.
"""
import sys
import os

# Ensure the project root is on sys.path so imports work from any CWD
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import customtkinter as ctk
from app.ui.main_window import MainWindow


def main() -> None:
    # Bootstrap runtime directories and JSON configurations first
    try:
        from app.utils.path_helper import bootstrap_runtime
        bootstrap_runtime()
    except Exception as e:
        print(f"Failed to run bootstrap: {e}")

    # Explicitly set the AppUserModelID to group taskbar window under our own application icon on Windows
    if sys.platform == "win32":
        try:
            import ctypes
            myappid = "CA2.DocumentComplianceChecker.1.0"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass

    from app.ui.theme import TM
    mode = TM.get_setting("appearance_mode", "System")
    ctk.set_appearance_mode(mode.lower())
    ctk.set_default_color_theme("blue")
    window = MainWindow()
    window.mainloop()


if __name__ == "__main__":
    main()
