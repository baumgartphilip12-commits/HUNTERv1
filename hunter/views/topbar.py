"""hunter/views/topbar.py — Top navigation bar."""

import tkinter as tk
from hunter.theme import THEME


class TopBar(tk.Frame):
    def __init__(self, parent, on_new_module, on_export_word, on_export_json,
                 on_export_questions, on_clear_plan, **kwargs):
        super().__init__(parent, bg=THEME["bg_panel"], height=56, **kwargs)
        self.pack_propagate(False)
        tk.Label(self, text="H  HUNTER", font=("Courier", 18, "bold"),
                 fg="#c1121f", bg=THEME["bg_panel"]).pack(side=tk.LEFT, padx=(16, 4))
        tk.Label(self, text="THREAT HUNT PLAN BUILDER", font=("Courier", 10, "bold"),
                 fg=THEME["accent"], bg=THEME["bg_panel"]).pack(side=tk.LEFT, padx=4)
        tk.Label(self, text="— Modular Hunt Planning & Questionnaire Generation",
                 font=("Courier", 9), fg=THEME["text_secondary"],
                 bg=THEME["bg_panel"]).pack(side=tk.LEFT, padx=4)
        bf = tk.Frame(self, bg=THEME["bg_panel"])
        bf.pack(side=tk.RIGHT, padx=16)
        self._btn(bf, "＋ New Module",      on_new_module)
        self._btn(bf, "⬇ Export Word",      on_export_word)
        self._btn(bf, "⬇ Export JSON",      on_export_json)
        self._btn(bf, "⬇ Export Questions", on_export_questions)
        self._btn(bf, "🗑 Clear Plan",       on_clear_plan, danger=True)

    @staticmethod
    def _btn(parent, text, cmd, danger=False):
        color = THEME["danger"] if danger else THEME["accent"]
        b = tk.Label(parent, text=text, font=("Courier", 9, "bold"),
                     fg=color, bg=THEME["bg_panel"], cursor="hand2", padx=10, pady=4)
        b.pack(side=tk.LEFT, padx=4)
        b.bind("<Button-1>", lambda e: cmd())
        b.bind("<Enter>",    lambda e: b.config(fg=THEME["bg_dark"], bg=color))
        b.bind("<Leave>",    lambda e: b.config(fg=color, bg=THEME["bg_panel"]))
        return b
