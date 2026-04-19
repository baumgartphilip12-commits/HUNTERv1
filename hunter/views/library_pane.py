"""hunter/views/library_pane.py — Left pane module library."""
import tkinter as tk
from hunter.theme import THEME, FILTER_CATS, CATEGORY_ICONS, PRIORITY_COLORS
from hunter.scroll import bind_scroll_recursive, rebind_scroll


class LibraryPane(tk.Frame):
    def __init__(self, parent, search_var, search_field_var, filter_category,
                 on_card_click, on_card_double_click, on_drag_motion, on_drag_release,
                 on_set_category, on_set_search_field, on_clear_search, **kwargs):
        super().__init__(parent, bg=THEME["bg_panel"], **kwargs)
        self._on_click        = on_card_click
        self._on_dbl          = on_card_double_click
        self._on_drag_motion  = on_drag_motion
        self._on_drag_release = on_drag_release
        self._on_set_cat      = on_set_category
        self._on_set_field    = on_set_search_field
        self._filter_cat      = filter_category
        self.card_widgets     = []
        self._cat_buttons     = {}
        self._field_buttons   = {}
        self._canvas          = None
        self.inner            = None
        self._win             = None
        self._count_lbl       = None
        self._build(search_var, search_field_var, on_clear_search)

    def _build(self, search_var, search_field_var, on_clear_search):
        hdr = tk.Frame(self, bg=THEME["bg_panel"])
        hdr.pack(fill=tk.X, padx=10, pady=(10, 6))
        tk.Label(hdr, text="MODULE LIBRARY", font=("Courier", 11, "bold"),
                 fg=THEME["text_primary"], bg=THEME["bg_panel"]).pack(side=tk.LEFT)
        self._count_lbl = tk.Label(hdr, text="", font=("Courier", 9),
                                    fg=THEME["text_secondary"], bg=THEME["bg_panel"])
        self._count_lbl.pack(side=tk.RIGHT)

        sf = tk.Frame(self, bg=THEME["bg_card"], highlightthickness=1,
                      highlightbackground=THEME["border"])
        sf.pack(fill=tk.X, padx=10, pady=(0, 2))
        tk.Label(sf, text="\u2315", font=("Courier", 11), fg=THEME["text_secondary"],
                 bg=THEME["bg_card"]).pack(side=tk.LEFT, padx=6)
        clr = tk.Label(sf, text="\u2715", font=("Courier", 10),
                       fg=THEME["text_muted"], bg=THEME["bg_card"], cursor="hand2", padx=4)
        clr.pack(side=tk.RIGHT, padx=4)
        clr.bind("<Button-1>", lambda e: on_clear_search())
        tk.Entry(sf, textvariable=search_var, font=("Courier", 10),
                 fg=THEME["text_primary"], bg=THEME["bg_card"],
                 insertbackground=THEME["accent"], bd=0, relief=tk.FLAT).pack(
            side=tk.LEFT, fill=tk.X, expand=True, pady=6)

        sff = tk.Frame(self, bg=THEME["bg_panel"])
        sff.pack(fill=tk.X, padx=10, pady=(0, 4))
        tk.Label(sff, text="Search in:", font=("Courier", 7),
                 fg=THEME["text_muted"], bg=THEME["bg_panel"]).pack(side=tk.LEFT, padx=(0, 4))
        for field in ("All Fields", "Name", "Tags", "MITRE"):
            rb = tk.Label(sff, text=field, font=("Courier", 7),
                          fg=THEME["text_secondary"], bg=THEME["bg_panel"],
                          cursor="hand2", padx=5, pady=2)
            rb.pack(side=tk.LEFT, padx=1)
            rb.bind("<Button-1>", lambda e, f=field: self._on_set_field(f))
            self._field_buttons[field] = rb
        self.highlight_field("All Fields")

        cf = tk.Frame(self, bg=THEME["bg_panel"])
        cf.pack(fill=tk.X, padx=10, pady=(0, 4))
        for cat in FILTER_CATS:
            b = tk.Label(cf, text=cat, font=("Courier", 7),
                         fg=THEME["text_secondary"], bg=THEME["bg_panel"],
                         cursor="hand2", padx=5, pady=3)
            b.pack(side=tk.LEFT, padx=1)
            b.bind("<Button-1>", lambda e, c=cat: self._on_set_cat(c))
            self._cat_buttons[cat] = b
        self.highlight_category("All")

        container = tk.Frame(self, bg=THEME["bg_panel"])
        container.pack(fill=tk.BOTH, expand=True, padx=6)
        self._canvas = tk.Canvas(container, bg=THEME["bg_panel"], bd=0, highlightthickness=0)
        sb = tk.Scrollbar(container, orient=tk.VERTICAL, command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._canvas.bind("<MouseWheel>",
            lambda e: self._canvas.yview_scroll(-1*(e.delta//120), "units"))
        self._canvas.bind("<Button-4>", lambda e: self._canvas.yview_scroll(-1, "units"))
        self._canvas.bind("<Button-5>", lambda e: self._canvas.yview_scroll(1, "units"))
        self.inner = tk.Frame(self._canvas, bg=THEME["bg_panel"])
        self._win  = self._canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>",
            lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")))

        # Do NOT update inner frame width during sash drag — that causes
        # tkinter to re-lay out all ~190 card widgets on every pixel moved.
        # Instead, freeze the width while dragging and apply it once on
        # ButtonRelease (mouse up = user finished resizing).
        def _apply_width():
            self._canvas.itemconfig(self._win, width=self._canvas.winfo_width())

        # Bind to the root window's ButtonRelease so we catch the sash release
        # regardless of which widget the cursor is over when the user lets go.
        self._canvas.winfo_toplevel().bind(
            "<ButtonRelease-1>",
            lambda e: _apply_width(),
            add="+"
        )

        tk.Label(self, text="\u2190 Drag to plan  |  Double-click to add",
                 font=("Courier", 8), fg=THEME["text_muted"],
                 bg=THEME["bg_panel"]).pack(pady=(2, 6))

    def refresh(self, modules: list, plan_ids: set) -> None:
        for w in self.inner.winfo_children():
            w.destroy()
        self.card_widgets.clear()
        self._count_lbl.config(text=f"{len(modules)} modules")
        for mod in modules:
            card = self._make_card(mod, mod["id"] in plan_ids)
            card.pack(fill=tk.X, padx=6, pady=3)
            self.card_widgets.append((card, mod))
        # Full recursive bind: every nested label/frame must be bound
        # or mousewheel stops working when cursor is over a child widget.
        bind_scroll_recursive(self.inner, self._canvas)

    def highlight_category(self, cat: str) -> None:
        for c, b in self._cat_buttons.items():
            b.config(fg=THEME["accent"] if c == cat else THEME["text_secondary"],
                     bg=THEME["bg_selected"] if c == cat else THEME["bg_panel"])

    def highlight_field(self, field: str) -> None:
        for f, b in self._field_buttons.items():
            b.config(fg=THEME["accent"] if f == field else THEME["text_secondary"],
                     bg=THEME["bg_selected"] if f == field else THEME["bg_panel"])

    def scroll_to_top(self) -> None:
        self._canvas.yview_moveto(0)

    def _make_card(self, mod: dict, in_plan: bool) -> tk.Frame:
        cat      = mod.get("category", "Other")
        cat_icon = CATEGORY_ICONS.get(cat, "\U0001f50d")
        is_apt   = cat == "APT"
        prio_col = PRIORITY_COLORS.get(mod.get("priority", "Medium"), THEME["warning"])
        bg       = THEME["bg_selected"] if in_plan else (
                   THEME["apt_bg"] if is_apt else THEME["bg_card"])
        border   = THEME["apt_border"] if is_apt else THEME["border"]

        outer    = tk.Frame(self.inner, bg=border, padx=1, pady=1)
        card     = tk.Frame(outer, bg=bg, padx=10, pady=8, cursor="hand2")
        card.pack(fill=tk.BOTH, expand=True)
        stripe   = tk.Frame(card, bg=prio_col, width=3)
        stripe.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        content  = tk.Frame(card, bg=bg)
        content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        title_row = tk.Frame(content, bg=bg)
        title_row.pack(fill=tk.X)
        name_lbl = tk.Label(title_row, text=f"{cat_icon} {mod['name']}",
                             font=("Courier", 10, "bold"),
                             fg=THEME["apt_text"] if is_apt else THEME["text_primary"],
                             bg=bg, anchor=tk.W)
        name_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
        status_lbl = None
        if in_plan:
            status_lbl = tk.Label(title_row, text="\u2713", font=("Courier", 9, "bold"),
                                   fg=THEME["success"], bg=bg)
            status_lbl.pack(side=tk.RIGHT)
        n_steps = sum(len(g["actions"]) for g in mod.get("hunt_actions", []))
        n_q     = len(mod.get("questions", []))
        meta_lbl = tk.Label(content,
            text=f"{mod.get('priority','?')}"
                 f" \u00b7 {mod.get('estimated_hours',0)}h"
                 f" \u00b7 {n_steps} steps \u00b7 {n_q} Qs",
            font=("Courier", 8), fg=THEME["text_secondary"], bg=bg, anchor=tk.W)
        meta_lbl.pack(fill=tk.X)
        tags_row   = tk.Frame(content, bg=bg)
        tags_row.pack(fill=tk.X, pady=(3, 0))
        tag_labels = []
        for tag in mod.get("tags", [])[:5]:
            tl = tk.Label(tags_row, text=tag, font=("Courier", 7),
                          fg=THEME["apt_text"] if is_apt else THEME["tag_text"],
                          bg=THEME["apt_border"] if is_apt else THEME["tag_bg"],
                          padx=4, pady=1)
            tl.pack(side=tk.LEFT, padx=1)
            tag_labels.append(tl)

        hover_targets = [card, content, title_row, tags_row]
        hover_bg = THEME["bg_card_hover"]

        def _enter(e):
            for w in hover_targets:
                try: w.config(bg=hover_bg)
                except Exception: pass

        def _leave(e):
            for w in hover_targets:
                try: w.config(bg=bg)
                except Exception: pass

        clickables = ([outer, card, stripe, content, title_row,
                       name_lbl, meta_lbl, tags_row] + tag_labels)
        if status_lbl:
            clickables.append(status_lbl)
        for w in clickables:
            w.bind("<Button-1>",        lambda e, m=mod: self._on_click(m))
            w.bind("<Double-Button-1>", lambda e, m=mod: self._on_dbl(m))
            w.bind("<B1-Motion>",       lambda e, m=mod: self._on_drag_motion(e, m))
            w.bind("<ButtonRelease-1>", lambda e, m=mod: self._on_drag_release(e, m))
            w.bind("<Enter>", _enter)
            w.bind("<Leave>", _leave)
        return outer
