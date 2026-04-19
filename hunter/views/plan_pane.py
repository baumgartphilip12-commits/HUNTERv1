"""hunter/views/plan_pane.py — Center pane: ordered hunt plan cards."""

import tkinter as tk
from hunter.theme import THEME, CATEGORY_ICONS, PRIORITY_COLORS
from hunter.scroll import bind_scroll_recursive, rebind_scroll


class PlanPane(tk.Frame):
    def __init__(self, parent, on_card_click, on_move, on_remove, on_edit, **kwargs):
        super().__init__(parent, bg=THEME["bg_dark"], **kwargs)
        self._on_card_click = on_card_click
        self._on_move       = on_move
        self._on_remove     = on_remove
        self._on_edit       = on_edit
        self.card_widgets   = []
        self._build()

    def _build(self):
        hdr = tk.Frame(self, bg=THEME["bg_panel"])
        hdr.pack(fill=tk.X, pady=(0, 6))
        lhdr = tk.Frame(hdr, bg=THEME["bg_panel"])
        lhdr.pack(side=tk.LEFT, padx=14, pady=8)
        tk.Label(lhdr, text="HUNT PLAN", font=("Courier", 11, "bold"),
                 fg=THEME["text_primary"], bg=THEME["bg_panel"]).pack(anchor=tk.W)
        self._subtitle = tk.Label(lhdr, text="0 modules  ·  0 steps  ·  0 questions",
                                   font=("Courier", 8), fg=THEME["text_secondary"],
                                   bg=THEME["bg_panel"])
        self._subtitle.pack(anchor=tk.W)
        container = tk.Frame(self, bg=THEME["bg_dark"])
        container.pack(fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(container, bg=THEME["bg_dark"], bd=0, highlightthickness=0)
        sb = tk.Scrollbar(container, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.canvas.bind("<MouseWheel>",
                         lambda e: self.canvas.yview_scroll(-1*(e.delta//120), "units"))
        self.canvas.bind("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"))
        self.canvas.bind("<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"))
        self.inner = tk.Frame(self.canvas, bg=THEME["bg_dark"])
        self._win  = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))

        # Freeze width during sash drag; apply once on mouse release.
        def _apply_width_plan():
            self.canvas.itemconfig(self._win, width=self.canvas.winfo_width())
        self.canvas.winfo_toplevel().bind(
            "<ButtonRelease-1>", lambda e: _apply_width_plan(), add="+")
        self._show_empty()

    def refresh(self, modules):
        for w in self.inner.winfo_children():
            w.destroy()
        self.card_widgets.clear()
        if not modules:
            self._show_empty()
        else:
            for i, mod in enumerate(modules):
                card = self._make_card(mod, i)
                card.pack(fill=tk.X, padx=10, pady=4)
                self.card_widgets.append((card, mod))
        steps = sum(len(g["actions"]) for m in modules for g in m.get("hunt_actions", []))
        qs    = sum(len(m.get("questions", [])) for m in modules)
        self._subtitle.config(
            text=f"{len(modules)} modules  ·  {steps} steps  ·  {qs} questions")

    def _show_empty(self):
        f = tk.Frame(self.inner, bg=THEME["bg_dark"])
        f.pack(fill=tk.BOTH, expand=True, pady=80)
        tk.Label(f, text="H", font=("Courier", 48, "bold"),
                 fg=THEME["critical"], bg=THEME["bg_dark"]).pack()
        tk.Label(f, text="No modules in plan", font=("Courier", 13, "bold"),
                 fg=THEME["text_muted"], bg=THEME["bg_dark"]).pack(pady=4)
        tk.Label(f, text="Double-click or drag modules from the library\nto build your hunt plan",
                 font=("Courier", 9), fg=THEME["text_muted"],
                 bg=THEME["bg_dark"], justify=tk.CENTER).pack()

    def _make_card(self, mod, idx):
        is_apt   = mod.get("category") == "APT"
        prio_col = PRIORITY_COLORS.get(mod.get("priority", "Medium"), THEME["warning"])
        cat_icon = CATEGORY_ICONS.get(mod.get("category", "Other"), "🔍")
        n_steps  = sum(len(g["actions"]) for g in mod.get("hunt_actions", []))
        n_q      = len(mod.get("questions", []))
        card_bg  = THEME["apt_bg"] if is_apt else THEME["bg_card"]
        border   = THEME["apt_border"] if is_apt else THEME["border_accent"]
        outer    = tk.Frame(self.inner, bg=border, padx=1, pady=1)
        card     = tk.Frame(outer, bg=card_bg, padx=12, pady=10)
        card.pack(fill=tk.BOTH, expand=True)
        top = tk.Frame(card, bg=card_bg)
        top.pack(fill=tk.X)
        badge = tk.Frame(top, bg=prio_col, width=28, height=28)
        badge.pack(side=tk.LEFT, padx=(0, 10))
        badge.pack_propagate(False)
        tk.Label(badge, text=str(idx+1), font=("Courier", 10, "bold"),
                 fg=THEME["bg_dark"], bg=prio_col).place(relx=.5, rely=.5, anchor=tk.CENTER)
        title_f = tk.Frame(top, bg=card_bg)
        title_f.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(title_f, text=f"{cat_icon} {mod['name']}", font=("Courier", 11, "bold"),
                 fg=THEME["apt_text"] if is_apt else THEME["text_primary"],
                 bg=card_bg, anchor=tk.W).pack(anchor=tk.W)
        tk.Label(title_f,
                 text=f"{mod.get('priority','?')} Priority  ·  "
                      f"{mod.get('estimated_hours',0)}h  ·  By {mod.get('author','?')}",
                 font=("Courier", 8), fg=THEME["text_secondary"],
                 bg=card_bg, anchor=tk.W).pack(anchor=tk.W)
        # Build ctrl frame but keep a reference so we can EXCLUDE it from
        # the card-select binding later — buttons must keep their own handlers.
        ctrl = tk.Frame(top, bg=card_bg)
        ctrl.pack(side=tk.RIGHT)
        self._ctrl_btn(ctrl, "✎", lambda m=mod: self._on_edit(m),    bg=card_bg)
        self._ctrl_btn(ctrl, "▲", lambda m=mod: self._on_move(m,-1), bg=card_bg)
        self._ctrl_btn(ctrl, "▼", lambda m=mod: self._on_move(m, 1), bg=card_bg)
        self._ctrl_btn(ctrl, "✕", lambda m=mod: self._on_remove(m),  bg=card_bg, danger=True)
        mid = tk.Frame(card, bg=card_bg)
        mid.pack(fill=tk.X, pady=(8, 0))
        for g in mod.get("hunt_actions", []):
            row = tk.Frame(mid, bg=card_bg)
            row.pack(fill=tk.X, pady=1)
            tk.Label(row, text="⬡", font=("Courier", 8),
                     fg=THEME["apt_text"] if is_apt else THEME["accent"],
                     bg=card_bg).pack(side=tk.LEFT)
            tk.Label(row, text=g["title"], font=("Courier", 9),
                     fg=THEME["apt_text"] if is_apt else THEME["accent_glow"],
                     bg=card_bg).pack(side=tk.LEFT, padx=4)
            tk.Label(row, text=f"({len(g['actions'])} steps)",
                     font=("Courier", 8), fg=THEME["text_muted"],
                     bg=card_bg).pack(side=tk.LEFT)
        stats = tk.Frame(card, bg=THEME["bg_dark"], padx=8, pady=4)
        stats.pack(fill=tk.X, pady=(8, 0))
        tk.Label(stats, text=f"{n_steps} steps", font=("Courier", 8),
                 fg=THEME["success"], bg=THEME["bg_dark"]).pack(side=tk.LEFT)
        tk.Label(stats, text="  |  ", font=("Courier", 8),
                 fg=THEME["text_muted"], bg=THEME["bg_dark"]).pack(side=tk.LEFT)
        tk.Label(stats, text=f"{n_q} questions", font=("Courier", 8),
                 fg=THEME["accent"], bg=THEME["bg_dark"]).pack(side=tk.LEFT)
        mitre = mod.get("mitre_techniques", [])
        if mitre:
            tk.Label(stats, text="  |  ", font=("Courier", 8),
                     fg=THEME["text_muted"], bg=THEME["bg_dark"]).pack(side=tk.LEFT)
            tk.Label(stats, text=" ".join(mitre[:3]), font=("Courier", 7),
                     fg=THEME["mitre_text"], bg=THEME["bg_dark"]).pack(side=tk.LEFT)

        # Bind card-select click on every widget EXCEPT the ctrl frame and its
        # children (✎ ▲ ▼ ✕).  Those buttons have their own commands set in
        # _ctrl_btn and must not be overwritten by the card-select handler.
        def _bind_click_recursive(widget, exclude=None):
            if exclude and widget is exclude:
                return   # skip this widget and all its children
            widget.bind("<Button-1>", lambda e, m=mod: self._on_card_click(m))
            for child in widget.winfo_children():
                _bind_click_recursive(child, exclude=exclude)
        _bind_click_recursive(outer, exclude=ctrl)
        return outer

    @staticmethod
    def _ctrl_btn(parent, text, cmd, bg=None, danger=False):
        bg    = bg or THEME["bg_card"]
        color = THEME["danger"] if danger else THEME["text_secondary"]
        b = tk.Label(parent, text=text, font=("Courier", 10),
                     fg=color, bg=bg, cursor="hand2", padx=4)
        b.pack(side=tk.LEFT)
        b.bind("<Button-1>", lambda e: cmd())
        b.bind("<Enter>",    lambda e: b.config(fg="#ffffff"))
        b.bind("<Leave>",    lambda e: b.config(fg=color))
