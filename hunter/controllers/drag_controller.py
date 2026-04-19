"""hunter/controllers/drag_controller.py — Drag-and-drop from library to plan."""

import tkinter as tk
from hunter.theme import THEME, CATEGORY_ICONS


class DragController:
    def __init__(self, plan_canvas, plan_inner, on_drop_callback):
        self._plan_canvas = plan_canvas
        self._plan_inner  = plan_inner
        self._on_drop     = on_drop_callback
        self._drag_module = None
        self._ghost       = None
        self._indicator   = None
        self._insert_idx  = None
        self._plan_cards  = []

    def set_plan_cards(self, cards):
        self._plan_cards = cards

    def on_motion(self, event, mod):
        if self._drag_module is None:
            self._drag_module = mod
            self._create_ghost(mod, event)
        if self._ghost:
            root = event.widget.winfo_toplevel()
            self._ghost.geometry(
                f"+{root.winfo_pointerx()+12}+{root.winfo_pointery()+8}")
        self._update_indicator()

    def on_release(self, event, mod):
        self._destroy_ghost()
        self._hide_indicator()
        if self._drag_module is None:
            return
        dragged, self._drag_module = self._drag_module, None
        if self._insert_idx is None:
            return
        idx, self._insert_idx = self._insert_idx, None
        self._on_drop(dragged, idx)

    def _create_ghost(self, mod, event):
        root = event.widget.winfo_toplevel()
        g = tk.Toplevel(root)
        g.overrideredirect(True)
        g.attributes("-alpha", 0.82)
        g.configure(bg=THEME["bg_selected"])
        try:
            g.attributes("-topmost", True)
        except Exception:
            pass
        f = tk.Frame(g, bg=THEME["bg_selected"], padx=10, pady=6,
                     highlightthickness=2,
                     highlightbackground=THEME["accent"])
        f.pack()
        icon = CATEGORY_ICONS.get(mod.get("category", "Other"), "🔍")
        tk.Label(f, text=f"{icon}  {mod['name']}",
                 font=("Courier", 10, "bold"),
                 fg=THEME["text_primary"],
                 bg=THEME["bg_selected"]).pack(anchor=tk.W)
        tk.Label(f, text="↓ drop into plan",
                 font=("Courier", 8),
                 fg=THEME["accent"],
                 bg=THEME["bg_selected"]).pack(anchor=tk.W)
        px = root.winfo_pointerx()
        py = root.winfo_pointery()
        g.geometry(f"+{px+12}+{py+8}")
        self._ghost = g

    def _destroy_ghost(self):
        if self._ghost:
            try:
                self._ghost.destroy()
            except Exception:
                pass
            self._ghost = None

    def _update_indicator(self):
        self._hide_indicator()
        pc     = self._plan_canvas
        root   = pc.winfo_toplevel()
        px, py = root.winfo_pointerx(), root.winfo_pointery()
        cx, cy = pc.winfo_rootx(), pc.winfo_rooty()
        cw, ch = pc.winfo_width(), pc.winfo_height()
        if not (cx <= px <= cx+cw and cy <= py <= cy+ch):
            self._insert_idx = None
            return
        rel_y      = py - cy + pc.yview()[0] * self._plan_inner.winfo_height()
        insert_idx = len(self._plan_cards)
        for i, (card_widget, _) in enumerate(self._plan_cards):
            if rel_y < card_widget.winfo_y() + card_widget.winfo_height() // 2:
                insert_idx = i
                break
        self._insert_idx = insert_idx
        self._indicator  = tk.Frame(self._plan_inner, bg=THEME["accent"], height=3)
        if self._plan_cards and insert_idx < len(self._plan_cards):
            y_pos = self._plan_cards[insert_idx][0].winfo_y() - 2
        elif self._plan_cards:
            last  = self._plan_cards[-1][0]
            y_pos = last.winfo_y() + last.winfo_height() + 2
        else:
            y_pos = 20
        w = max(self._plan_inner.winfo_width() - 20, 10)
        self._indicator.place(x=10, y=y_pos, width=w, height=3)
        self._indicator.lift()

    def _hide_indicator(self):
        if self._indicator is not None:
            try:
                self._indicator.place_forget()
                self._indicator.destroy()
            except Exception:
                pass
            self._indicator = None
