"""
HUNTER — Threat Hunt Plan Builder
Entry point. Run with:  python main.py
"""

# ── Suppress noisy-but-harmless interpreter warnings ─────────────────────────
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=ResourceWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# ── Windows HiDPI: declare DPI awareness before Tk initialises ───────────────
import sys
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

# ── Launch ────────────────────────────────────────────────────────────────────
from hunter.app import HunterApp

if __name__ == "__main__":
    app = HunterApp()
    app.mainloop()
