"""
hunter/views/detail_pane.py
Right pane: scrollable module detail view with clickable MITRE chips.
"""

import webbrowser
import tkinter as tk
from hunter.theme import THEME, CATEGORY_ICONS, PRIORITY_COLORS
from hunter.scroll import bind_scroll_recursive, rebind_scroll


class DetailPane(tk.Frame):
    """Displays full details of the currently selected module."""

    def __init__(self, parent: tk.Widget,
                 on_add_to_plan,
                 on_remove_from_plan,
                 on_edit_module,
                 on_mitre_click,
                 **kwargs):
        super().__init__(parent, bg=THEME["bg_panel"], **kwargs)
        self._on_add    = on_add_to_plan
        self._on_remove = on_remove_from_plan
        self._on_edit   = on_edit_module
        self._on_mitre  = on_mitre_click

        self._build()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self):
        tk.Label(self, text="MODULE DETAILS", font=("Courier", 11, "bold"),
                 fg=THEME["text_primary"],
                 bg=THEME["bg_panel"]).pack(anchor=tk.W, padx=10, pady=(10, 6))

        container = tk.Frame(self, bg=THEME["bg_panel"])
        container.pack(fill=tk.BOTH, expand=True, padx=4)

        self._canvas = tk.Canvas(container, bg=THEME["bg_panel"],
                                  bd=0, highlightthickness=0)
        sb = tk.Scrollbar(container, orient=tk.VERTICAL,
                          command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._canvas.bind("<MouseWheel>",
                          lambda e: self._canvas.yview_scroll(-1*(e.delta//120), "units"))
        self._canvas.bind("<Button-4>",
                          lambda e: self._canvas.yview_scroll(-1, "units"))
        self._canvas.bind("<Button-5>",
                          lambda e: self._canvas.yview_scroll(1, "units"))

        self.inner = tk.Frame(self._canvas, bg=THEME["bg_panel"])
        self._win  = self._canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>",
                        lambda e: self._canvas.configure(
                            scrollregion=self._canvas.bbox("all")))

        # Freeze width during sash drag; apply once on mouse release.
        def _apply_width_detail():
            self._canvas.itemconfig(self._win, width=self._canvas.winfo_width())
        self._canvas.winfo_toplevel().bind(
            "<ButtonRelease-1>", lambda e: _apply_width_detail(), add="+")

        self.show_empty()

    # ── Public ────────────────────────────────────────────────────────────────

    def show_empty(self):
        for w in self.inner.winfo_children():
            w.destroy()
        tk.Label(self.inner, text="Select a module\nto view its details",
                 font=("Courier", 10), fg=THEME["text_muted"],
                 bg=THEME["bg_panel"], justify=tk.CENTER).pack(pady=60)

    def show_module(self, mod: dict, in_plan: bool) -> None:
        for w in self.inner.winfo_children():
            w.destroy()
        p      = self.inner
        bg     = THEME["bg_panel"]
        is_apt = mod.get("category") == "APT"
        hdr_bg = THEME["apt_bg"] if is_apt else THEME["bg_card"]
        hdr_fg = THEME["apt_text"] if is_apt else THEME["text_primary"]

        # ── Helper closures ──
        def shdr(text, color=THEME["accent"]):
            tk.Frame(p, bg=THEME["border"], height=1).pack(
                fill=tk.X, padx=10, pady=(12, 0))
            tk.Label(p, text=text, font=("Courier", 9, "bold"),
                     fg=color, bg=bg, anchor=tk.W).pack(
                fill=tk.X, padx=10, pady=(3, 2))

        def irow(label, value, vc=THEME["text_primary"]):
            f = tk.Frame(p, bg=bg)
            f.pack(fill=tk.X, padx=10, pady=1)
            tk.Label(f, text=label, font=("Courier", 8),
                     fg=THEME["text_secondary"], bg=bg,
                     width=16, anchor=tk.W).pack(side=tk.LEFT)
            tk.Label(f, text=value, font=("Courier", 8), fg=vc, bg=bg,
                     anchor=tk.W, wraplength=240,
                     justify=tk.LEFT).pack(side=tk.LEFT)

        prio_col = PRIORITY_COLORS.get(mod.get("priority", "Medium"), THEME["warning"])
        cat_icon = CATEGORY_ICONS.get(mod.get("category", "Other"), "🔍")

        # Header card
        hf = tk.Frame(p, bg=hdr_bg, padx=12, pady=12)
        hf.pack(fill=tk.X, padx=6, pady=6)
        if is_apt:
            tk.Label(hf, text="⚠  NATION STATE THREAT ACTOR",
                     font=("Courier", 8, "bold"),
                     fg=THEME["apt_text"], bg=hdr_bg).pack(
                anchor=tk.W, pady=(0, 4))
        tk.Label(hf, text=f"{cat_icon} {mod['name']}",
                 font=("Courier", 12, "bold"),
                 fg=hdr_fg, bg=hdr_bg, anchor=tk.W,
                 wraplength=340).pack(fill=tk.X)
        mr = tk.Frame(hf, bg=hdr_bg)
        mr.pack(fill=tk.X, pady=(4, 0))
        tk.Label(mr, text=mod.get("priority", "?"),
                 font=("Courier", 8, "bold"),
                 fg=prio_col, bg=hdr_bg).pack(side=tk.LEFT)
        tk.Label(mr, text=f"  {mod.get('category','?')}  ·  ~{mod.get('estimated_hours',0)}h",
                 font=("Courier", 8), fg=THEME["text_secondary"],
                 bg=hdr_bg).pack(side=tk.LEFT)
        tf = tk.Frame(hf, bg=hdr_bg)
        tf.pack(fill=tk.X, pady=(6, 0))
        for tag in mod.get("tags", []):
            tk.Label(tf, text=tag, font=("Courier", 7),
                     fg=THEME["apt_text"] if is_apt else THEME["tag_text"],
                     bg=THEME["apt_border"] if is_apt else THEME["tag_bg"],
                     padx=4, pady=1).pack(side=tk.LEFT, padx=1, pady=1)

        shdr("METADATA")
        irow("Author:",       mod.get("author", "Unknown"))
        irow("Last Updated:", mod.get("last_updated", "?"), THEME["text_secondary"])
        irow("Module ID:",    mod.get("id", "?"), THEME["text_muted"])

        # MITRE chips
        mitre = mod.get("mitre_techniques", [])
        if mitre:
            shdr("MITRE ATT&CK", THEME["mitre_text"])
            tk.Label(p,
                     text="  Left-click: filter library  ·  Right-click: open ATT&CK website",
                     font=("Courier", 7), fg=THEME["text_muted"],
                     bg=bg, anchor=tk.W).pack(fill=tk.X, padx=10)
            mf = tk.Frame(p, bg=bg)
            mf.pack(fill=tk.X, padx=10, pady=4, anchor=tk.W)
            for t in mitre:
                chip = tk.Label(mf, text=t, font=("Courier", 8),
                                fg=THEME["mitre_text"], bg=THEME["mitre_bg"],
                                padx=5, pady=2, cursor="hand2")
                chip.pack(side=tk.LEFT, padx=2)
                chip.bind("<Button-1>", lambda e, c=t: self._on_mitre(c))
                chip.bind("<Button-3>", lambda e, c=t: self._open_mitre_url(c))
                chip.bind("<Enter>", lambda e, c=chip: c.config(
                    fg=THEME["bg_dark"], bg=THEME["mitre_text"]))
                chip.bind("<Leave>", lambda e, c=chip: c.config(
                    fg=THEME["mitre_text"], bg=THEME["mitre_bg"]))

        # Prerequisites
        prereqs = mod.get("prerequisites", [])
        if prereqs:
            shdr("PREREQUISITES", THEME["warning"])
            for pr in prereqs:
                f = tk.Frame(p, bg=bg)
                f.pack(fill=tk.X, padx=10, pady=1)
                tk.Label(f, text="⚠", font=("Courier", 8),
                         fg=THEME["warning"], bg=bg).pack(side=tk.LEFT)
                tk.Label(f, text=pr, font=("Courier", 8),
                         fg=THEME["text_secondary"], bg=bg,
                         wraplength=300, justify=tk.LEFT).pack(
                    side=tk.LEFT, padx=4)

        # Required tools
        tools = mod.get("required_tools", [])
        if tools:
            shdr("REQUIRED TOOLS", THEME["accent"])
            for t in tools:
                rf = tk.Frame(p, bg=bg)
                rf.pack(fill=tk.X, padx=10, pady=2)
                tk.Label(rf, text="▸", font=("Courier", 8),
                         fg=THEME["accent"], bg=bg,
                         width=2, anchor=tk.NW).pack(
                    side=tk.LEFT, anchor=tk.NW, pady=1)
                lbl = tk.Label(rf, text=t, font=("Courier", 8),
                               fg=THEME["text_primary"], bg=bg,
                               justify=tk.LEFT, anchor=tk.W)
                lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=1)
                lbl.bind("<Configure>",
                         lambda e, l=lbl: l.config(
                             wraplength=max(e.width - 6, 60)))

        # Hunt actions
        shdr("HUNT ACTIONS",
             THEME["apt_text"] if is_apt else THEME["success"])
        for g in mod.get("hunt_actions", []):
            gf = tk.Frame(p, bg=hdr_bg, padx=10, pady=6)
            gf.pack(fill=tk.X, padx=10, pady=3)
            tk.Label(gf, text=g["title"], font=("Courier", 9, "bold"),
                     fg=THEME["apt_text"] if is_apt else THEME["accent_glow"],
                     bg=hdr_bg).pack(anchor=tk.W)
            for i, action in enumerate(g["actions"], 1):
                af = tk.Frame(gf, bg=hdr_bg)
                af.pack(fill=tk.X, pady=2)
                tk.Label(af, text=f"{i}.", font=("Courier", 8, "bold"),
                         fg=THEME["apt_text"] if is_apt else THEME["success"],
                         bg=hdr_bg, width=3, anchor=tk.E).pack(
                    side=tk.LEFT, anchor=tk.NW)
                tk.Label(af, text=action, font=("Courier", 8),
                         fg=THEME["text_secondary"], bg=hdr_bg,
                         wraplength=310, justify=tk.LEFT,
                         anchor=tk.W).pack(
                    side=tk.LEFT, fill=tk.X, expand=True, padx=4)

        # Questionnaire items
        shdr("QUESTIONNAIRE ITEMS", THEME["accent"])
        for i, q in enumerate(mod.get("questions", []), 1):
            qf = tk.Frame(p, bg=THEME["bg_card"], padx=8, pady=5)
            qf.pack(fill=tk.X, padx=10, pady=2)
            num = tk.Frame(qf, bg=THEME["accent_dim"], width=20)
            num.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 6))
            num.pack_propagate(False)
            tk.Label(num, text=str(i), font=("Courier", 7, "bold"),
                     fg=THEME["bg_dark"],
                     bg=THEME["accent_dim"]).pack(fill=tk.BOTH, expand=True)
            tk.Label(qf, text=q, font=("Courier", 8),
                     fg=THEME["text_primary"], bg=THEME["bg_card"],
                     wraplength=310, justify=tk.LEFT,
                     anchor=tk.W).pack(side=tk.LEFT, fill=tk.X, expand=True)

        # References
        refs = mod.get("references", [])
        if refs:
            shdr("REFERENCES", THEME["text_secondary"])
            for r in refs:
                tk.Label(p, text=f"  {r}", font=("Courier", 7),
                         fg=THEME["accent_dim"], bg=bg,
                         anchor=tk.W, wraplength=360).pack(
                    fill=tk.X, padx=10, pady=1)

        # Action buttons
        bf = tk.Frame(p, bg=bg)
        bf.pack(fill=tk.X, padx=10, pady=(12, 6))

        eb = tk.Label(bf, text="✎  Edit Module",
                      font=("Courier", 9, "bold"),
                      fg=THEME["warning"], bg=THEME["bg_card"],
                      cursor="hand2", padx=10, pady=6)
        eb.pack(fill=tk.X, pady=2)
        eb.bind("<Button-1>", lambda e, m=mod: self._on_edit(m))

        if in_plan:
            rb = tk.Label(bf, text="✕  Remove from Plan",
                          font=("Courier", 9, "bold"),
                          fg=THEME["danger"], bg=THEME["bg_card"],
                          cursor="hand2", padx=10, pady=6)
            rb.pack(fill=tk.X, pady=2)
            rb.bind("<Button-1>", lambda e, m=mod: self._on_remove(m))
        else:
            ab = tk.Label(bf, text="＋  Add to Hunt Plan",
                          font=("Courier", 9, "bold"),
                          fg=THEME["bg_dark"], bg=THEME["accent"],
                          cursor="hand2", padx=10, pady=6)
            ab.pack(fill=tk.X, pady=2)
            ab.bind("<Button-1>", lambda e, m=mod: self._on_add(m))

        self._canvas.yview_moveto(0)
        # Full recursive bind so scroll works over every nested label.
        bind_scroll_recursive(self.inner, self._canvas)

    # ── Static helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _open_mitre_url(code: str) -> None:
        code = code.strip()
        if "." in code:
            base, sub = code.split(".", 1)
            url = f"https://attack.mitre.org/techniques/{base}/{sub}/"
        else:
            url = f"https://attack.mitre.org/techniques/{code}/"
        webbrowser.open(url)
