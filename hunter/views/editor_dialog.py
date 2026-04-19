"""
hunter/views/editor_dialog.py
Modal dialog for creating or editing a hunt module.
"""

import tkinter as tk
from tkinter import messagebox
from datetime import datetime
import uuid

from hunter.theme import THEME, CATEGORIES, PRIORITIES
from hunter.scroll import rebind_scroll


class ModuleEditorDialog(tk.Toplevel):
    """Create or edit a hunt module with grouped action steps."""

    def __init__(self, parent: tk.Widget, callback, existing: dict | None = None):
        super().__init__(parent)
        self.callback = callback
        self.existing = existing
        self.is_edit  = existing is not None

        self.title("Edit Module" if self.is_edit else "Create New Hunt Module")
        self.configure(bg=THEME["bg_dark"])
        self.geometry("880x760")
        self.resizable(True, True)
        self.grab_set()

        # State
        self.hunt_action_groups: list[dict] = []
        self.questions_list:     list       = []

        self._build_ui()
        if self.is_edit:
            self._populate(existing)

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        hdr = tk.Frame(self, bg=THEME["bg_panel"], pady=12)
        hdr.pack(fill=tk.X)
        tk.Label(hdr,
                 text=f"{'✎  EDIT' if self.is_edit else '＋  NEW'} HUNT MODULE",
                 font=("Courier", 13, "bold"), fg=THEME["accent"],
                 bg=THEME["bg_panel"]).pack(padx=20, anchor=tk.W)
        tk.Label(hdr,
                 text="Each action group = one objective. One step per entry box.",
                 font=("Courier", 9), fg=THEME["text_secondary"],
                 bg=THEME["bg_panel"]).pack(padx=20, anchor=tk.W)

        self._canvas = tk.Canvas(self, bg=THEME["bg_dark"],
                                  bd=0, highlightthickness=0)
        esb = tk.Scrollbar(self, orient=tk.VERTICAL, command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=esb.set)
        esb.pack(side=tk.RIGHT, fill=tk.Y)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.body = tk.Frame(self._canvas, bg=THEME["bg_dark"], padx=20, pady=10)
        self._win  = self._canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.body.bind("<Configure>",
                       lambda e: self._canvas.configure(
                           scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>",
                          lambda e: self._canvas.itemconfig(
                              self._win, width=e.width - 20))

        def _scroll(e):
            if e.num == 4:   self._canvas.yview_scroll(-1, "units")
            elif e.num == 5: self._canvas.yview_scroll(1, "units")
            elif e.delta:    self._canvas.yview_scroll(-1*(e.delta//120), "units")
        self._canvas.bind("<MouseWheel>", _scroll)
        self._canvas.bind("<Button-4>",   _scroll)
        self._canvas.bind("<Button-5>",   _scroll)

        self._text_field("Module Name:",      "module_name")
        self._dropdown_field("Category:",     "category",  CATEGORIES)
        self._text_field("Author:",           "author")
        self._dropdown_field("Priority:",     "priority",  PRIORITIES)
        self._text_field("Est. Hours:",       "est_hours", hint="integer e.g. 4")
        self._text_field("MITRE Techniques:", "mitre",
                         hint="e.g. T1078, T1566 (comma-separated)")
        self._text_field("Prerequisites:",    "prereqs",   hint="comma-separated")
        self._text_field("Required Tools:",   "tools_req", hint="comma-separated")
        self._text_field("Tags:",             "tags",      hint="comma-separated")
        self._text_field("References:",       "refs",      hint="URLs comma-separated")

        # Hunt action groups
        tk.Label(self.body, text="HUNT ACTION GROUPS",
                 font=("Courier", 9, "bold"), fg=THEME["accent"],
                 bg=THEME["bg_dark"]).pack(anchor=tk.W, pady=(16, 2))
        tk.Label(self.body,
                 text="One group per hunt objective.  One step per entry box.\n"
                      "Use '＋ Add Step' to add more steps inside a group.",
                 font=("Courier", 8), fg=THEME["text_muted"],
                 bg=THEME["bg_dark"], justify=tk.LEFT).pack(anchor=tk.W)

        self.actions_frame = tk.Frame(self.body, bg=THEME["bg_dark"])
        self.actions_frame.pack(fill=tk.X, pady=4)
        self._add_action_group()

        ag_btn = tk.Label(self.body, text="＋ Add Action Group",
                          font=("Courier", 8, "bold"), fg=THEME["accent"],
                          bg=THEME["bg_dark"], cursor="hand2")
        ag_btn.pack(anchor=tk.W, pady=(0, 4))
        ag_btn.bind("<Button-1>", lambda e: self._add_action_group())

        tk.Label(self.body, text="QUESTIONNAIRE ITEMS",
                 font=("Courier", 9, "bold"), fg=THEME["accent"],
                 bg=THEME["bg_dark"]).pack(anchor=tk.W, pady=(16, 2))
        self.q_frame = tk.Frame(self.body, bg=THEME["bg_dark"])
        self.q_frame.pack(fill=tk.X)
        self._add_question()

        q_btn = tk.Label(self.body, text="＋ Add Question",
                         font=("Courier", 8, "bold"), fg=THEME["accent"],
                         bg=THEME["bg_dark"], cursor="hand2")
        q_btn.pack(anchor=tk.W, pady=4)
        q_btn.bind("<Button-1>", lambda e: self._add_question())

        lbl = "  ✔  SAVE CHANGES  " if self.is_edit else "  ✔  SAVE MODULE  "
        sv = tk.Label(self.body, text=lbl, font=("Courier", 10, "bold"),
                      fg=THEME["bg_dark"], bg=THEME["accent"],
                      cursor="hand2", padx=10, pady=8)
        sv.pack(pady=20, anchor=tk.W)
        sv.bind("<Button-1>", lambda e: self._save())

    def _rewire(self):
        rebind_scroll(self.body, self._canvas)

    # ── Field helpers ─────────────────────────────────────────────────────────

    def _text_field(self, label: str, attr: str, hint: str = ""):
        f = tk.Frame(self.body, bg=THEME["bg_dark"])
        f.pack(fill=tk.X, pady=3)
        tk.Label(f, text=label, font=("Courier", 8, "bold"),
                 fg=THEME["text_secondary"], bg=THEME["bg_dark"],
                 width=20, anchor=tk.W).pack(side=tk.LEFT)
        var = tk.StringVar()
        tk.Entry(f, textvariable=var, font=("Courier", 9),
                 fg=THEME["text_primary"], bg=THEME["bg_card"],
                 insertbackground=THEME["accent"], bd=0, relief=tk.FLAT,
                 highlightthickness=1, highlightbackground=THEME["border"],
                 highlightcolor=THEME["accent"]).pack(
            side=tk.LEFT, fill=tk.X, expand=True, ipady=4, padx=4)
        if hint:
            tk.Label(f, text=hint, font=("Courier", 7),
                     fg=THEME["text_muted"],
                     bg=THEME["bg_dark"]).pack(side=tk.LEFT, padx=4)
        setattr(self, attr, var)

    def _dropdown_field(self, label: str, attr: str, options: list[str]):
        f = tk.Frame(self.body, bg=THEME["bg_dark"])
        f.pack(fill=tk.X, pady=3)
        tk.Label(f, text=label, font=("Courier", 8, "bold"),
                 fg=THEME["text_secondary"], bg=THEME["bg_dark"],
                 width=20, anchor=tk.W).pack(side=tk.LEFT)
        var = tk.StringVar(value=options[0])
        om = tk.OptionMenu(f, var, *options)
        om.config(font=("Courier", 9), fg=THEME["text_primary"],
                  bg=THEME["bg_card"], activebackground=THEME["bg_selected"],
                  activeforeground=THEME["accent"], bd=0, relief=tk.FLAT,
                  highlightthickness=1, highlightbackground=THEME["border"],
                  indicatoron=True, width=18)
        om["menu"].config(font=("Courier", 9), bg=THEME["bg_card"],
                          fg=THEME["text_primary"],
                          activebackground=THEME["accent"],
                          activeforeground=THEME["bg_dark"])
        om.pack(side=tk.LEFT, padx=4)
        setattr(self, attr, var)

    # ── Action group management ───────────────────────────────────────────────

    def _add_action_group(self, title: str = "", actions: list[str] | None = None):
        if actions is None:
            actions = [""]
        gf = tk.Frame(self.actions_frame, bg=THEME["bg_card"],
                       padx=10, pady=8, highlightthickness=1,
                       highlightbackground=THEME["border_accent"])
        gf.pack(fill=tk.X, pady=4)

        tf = tk.Frame(gf, bg=THEME["bg_card"])
        tf.pack(fill=tk.X)
        tk.Label(tf, text="Group Title:", font=("Courier", 8, "bold"),
                 fg=THEME["accent_glow"], bg=THEME["bg_card"]).pack(side=tk.LEFT)
        title_var = tk.StringVar(value=title)
        tk.Entry(tf, textvariable=title_var, font=("Courier", 9),
                 fg=THEME["text_primary"], bg=THEME["bg_dark"],
                 insertbackground=THEME["accent"], bd=0, relief=tk.FLAT,
                 highlightthickness=1,
                 highlightbackground=THEME["border"]).pack(
            side=tk.LEFT, fill=tk.X, expand=True, ipady=3, padx=(6, 0))

        rm_lbl = tk.Label(tf, text=" ✕ Remove Group", font=("Courier", 7),
                          fg=THEME["danger"], bg=THEME["bg_card"], cursor="hand2")
        rm_lbl.pack(side=tk.RIGHT, padx=6)

        steps_frame = tk.Frame(gf, bg=THEME["bg_card"])
        steps_frame.pack(fill=tk.X, pady=(6, 0))

        gd = {"title_var": title_var, "action_vars": [],
              "frame": gf, "steps_frame": steps_frame}
        self.hunt_action_groups.append(gd)
        rm_lbl.bind("<Button-1>", lambda e, g=gd: self._remove_group(g))

        for act in actions:
            self._add_step(gd, value=act)

        add_step = tk.Label(gf, text="  ＋ Add Step",
                            font=("Courier", 7, "bold"),
                            fg=THEME["accent"], bg=THEME["bg_card"],
                            cursor="hand2")
        add_step.pack(anchor=tk.W, pady=(4, 0))
        add_step.bind("<Button-1>", lambda e, g=gd: self._add_step(g))
        self._rewire()

    def _add_step(self, gd: dict, value: str = ""):
        idx = len(gd["action_vars"]) + 1
        row = tk.Frame(gd["steps_frame"], bg=THEME["bg_card"])
        row.pack(fill=tk.X, pady=2)
        tk.Label(row, text=f"Step {idx}:", font=("Courier", 7, "bold"),
                 fg=THEME["accent_dim"], bg=THEME["bg_card"],
                 width=8, anchor=tk.W).pack(side=tk.LEFT)
        var = tk.StringVar(value=value)
        tk.Entry(row, textvariable=var, font=("Courier", 8),
                 fg=THEME["text_primary"], bg=THEME["bg_dark"],
                 insertbackground=THEME["accent"], bd=0, relief=tk.FLAT,
                 highlightthickness=1,
                 highlightbackground=THEME["border"]).pack(
            side=tk.LEFT, fill=tk.X, expand=True, ipady=4, padx=4)
        rm = tk.Label(row, text="✕", font=("Courier", 8),
                      fg=THEME["text_muted"], bg=THEME["bg_card"],
                      cursor="hand2")
        rm.pack(side=tk.RIGHT, padx=4)
        rm.bind("<Button-1>", lambda e, r=row, v=var, g=gd:
                self._remove_step(r, v, g))
        gd["action_vars"].append(var)
        self._rewire()

    def _remove_step(self, row_frame, var, gd):
        if len(gd["action_vars"]) <= 1:
            messagebox.showwarning("Cannot Remove",
                                   "Each group must have at least one step.",
                                   parent=self)
            return
        gd["action_vars"].remove(var)
        row_frame.destroy()
        self._rewire()

    def _remove_group(self, gd):
        gd["frame"].destroy()
        self.hunt_action_groups.remove(gd)
        self._rewire()

    def _add_question(self, value: str = ""):
        qf = tk.Frame(self.q_frame, bg=THEME["bg_dark"])
        qf.pack(fill=tk.X, pady=2)
        idx = len(self.questions_list) + 1
        tk.Label(qf, text=f"Q{idx:02d}.", font=("Courier", 8, "bold"),
                 fg=THEME["accent_dim"], bg=THEME["bg_dark"],
                 width=5).pack(side=tk.LEFT)
        var = tk.StringVar(value=value)
        tk.Entry(qf, textvariable=var, font=("Courier", 9),
                 fg=THEME["text_primary"], bg=THEME["bg_card"],
                 insertbackground=THEME["accent"], bd=0, relief=tk.FLAT,
                 highlightthickness=1,
                 highlightbackground=THEME["border"]).pack(
            side=tk.LEFT, fill=tk.X, expand=True, ipady=4, padx=4)
        self.questions_list.append(var)
        self._rewire()

    # ── Populate from existing ────────────────────────────────────────────────

    def _populate(self, mod: dict):
        self.module_name.set(mod.get("name", ""))
        cat = mod.get("category", "Cloud")
        self.category.set(cat if cat in CATEGORIES else "Other")
        self.author.set(mod.get("author", ""))
        pri = mod.get("priority", "High")
        self.priority.set(pri if pri in PRIORITIES else "High")
        self.est_hours.set(str(mod.get("estimated_hours", "")))
        self.mitre.set(", ".join(mod.get("mitre_techniques", [])))
        self.prereqs.set(", ".join(mod.get("prerequisites", [])))
        self.tools_req.set(", ".join(mod.get("required_tools", [])))
        self.tags.set(", ".join(mod.get("tags", [])))
        self.refs.set(", ".join(mod.get("references", [])))

        for w in self.actions_frame.winfo_children():
            w.destroy()
        self.hunt_action_groups.clear()
        for g in mod.get("hunt_actions", []):
            self._add_action_group(title=g.get("title", ""),
                                   actions=g.get("actions", [""]))
        if not self.hunt_action_groups:
            self._add_action_group()

        for w in self.q_frame.winfo_children():
            w.destroy()
        self.questions_list.clear()
        for q in mod.get("questions", []):
            self._add_question(value=q)
        if not self.questions_list:
            self._add_question()

    # ── Save ─────────────────────────────────────────────────────────────────

    def _save(self):
        name = self.module_name.get().strip()
        if not name:
            messagebox.showwarning("Required", "Module name is required.",
                                   parent=self)
            return

        def csv(t):
            return [x.strip() for x in t.split(",") if x.strip()]

        hunt_actions = [
            {"title": gd["title_var"].get().strip(),
             "actions": [v.get().strip() for v in gd["action_vars"]
                         if v.get().strip()]}
            for gd in self.hunt_action_groups
            if gd["title_var"].get().strip()
        ]
        questions = [v.get().strip() for v in self.questions_list
                     if v.get().strip()]

        mod_id = (self.existing["id"] if self.is_edit
                  else f"mod_{name.lower().replace(' ','_')}_{uuid.uuid4().hex[:6]}")

        mod: dict = {
            "id":               mod_id,
            "name":             name,
            "category":         self.category.get(),
            "author":           self.author.get().strip() or "Unknown",
            "last_updated":     datetime.now().strftime("%Y-%m-%d"),
            "priority":         self.priority.get(),
            "estimated_hours":  int(self.est_hours.get().strip() or 1),
            "mitre_techniques": csv(self.mitre.get()),
            "prerequisites":    csv(self.prereqs.get()),
            "required_tools":   csv(self.tools_req.get()),
            "tags":             csv(self.tags.get()),
            "references":       csv(self.refs.get()),
            "hunt_actions":     hunt_actions,
            "questions":        questions,
        }
        if self.is_edit and self.existing and "_filepath" in self.existing:
            mod["_filepath"] = self.existing["_filepath"]

        self.callback(mod)
        self.destroy()
