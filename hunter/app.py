"""
hunter/app.py
=============
HunterApp — the root Tk window and application orchestrator.

This is the single file that knows about every controller and every view.
All other modules are kept deliberately ignorant of each other; they
communicate only through callbacks passed in at construction time.

Architecture summary
--------------------
Views (library_pane, plan_pane, detail_pane, topbar, editor_dialog):
    Pure UI.  Receive data and callbacks; fire callbacks upward.
    Never import controllers directly.

Controllers (plan, search, drag, export):
    Pure logic.  Hold state or perform I/O; no tkinter widget creation.

app.py:
    Wires views to controllers.  All callback implementations live here.
    Think of it as the "presenter" layer in a passive-view MVC pattern.
"""

import tkinter as tk
import os

from hunter.theme import THEME
from hunter.scroll import bind_scroll_recursive

# Model / persistence
from hunter.models.module_store import (
    load_modules_from_disk,
    save_module_to_disk,
    cache_search_fields,
)

# Controllers — logic with no UI imports
from hunter.controllers.plan_controller   import PlanController
from hunter.controllers.search_controller import SearchController
from hunter.controllers.drag_controller  import DragController
from hunter.controllers.export_controller import ExportController

# Views — UI widgets with no controller imports
from hunter.views.topbar        import TopBar
from hunter.views.library_pane  import LibraryPane
from hunter.views.plan_pane     import PlanPane
from hunter.views.detail_pane   import DetailPane
from hunter.views.editor_dialog import ModuleEditorDialog


class HunterApp(tk.Tk):
    """Root application window.

    Responsibilities:
    - Create and configure the main window.
    - Instantiate all controllers and views.
    - Wire views to controllers via callback arguments.
    - Implement all callback methods that mutate application state.
    """

    def __init__(self):
        super().__init__()
        self.title("HUNTER — Threat Hunt Plan Builder")
        self.geometry("1540x920")
        self.minsize(1200, 700)
        self.configure(bg=THEME["bg_dark"])

        # ── Locate the project root ───────────────────────────────────────────
        # __file__ is  hunter/app.py
        # dirname()  → hunter/          (the Python package folder)
        # dirname()  → project root     (where main.py and export_docx.js live)
        _here            = os.path.abspath(__file__)          # hunter/app.py
        _package_dir     = os.path.dirname(_here)             # hunter/
        self._script_dir = os.path.dirname(_package_dir)      # project root

        # ── Application state ─────────────────────────────────────────────────
        # All available module dicts loaded from the modules/ directory
        self.available_modules: list[dict] = load_modules_from_disk()
        # The module currently shown in the detail pane (None if nothing selected)
        self.selected_module: dict | None = None

        # ── Controllers ───────────────────────────────────────────────────────
        self.plan   = PlanController()    # manages the ordered hunt plan list
        self.search = SearchController()  # manages search query and filtering

        # ── Shared tkinter variables ──────────────────────────────────────────
        # StringVars are created here and passed into views so app.py remains
        # the single source of truth for these values.
        self.search_var       = tk.StringVar()                 # search bar text
        self.search_field_var = tk.StringVar(value="All Fields")  # field selector
        self.filter_category  = tk.StringVar(value="All")     # category filter

        # Debounce: cancel the previous timer and set a new one on every keystroke
        # so the library only rebuilds 120 ms after the user stops typing.
        self._search_after_id: str | None = None
        self.search_var.trace_add("write", lambda *_: self._debounced_refresh())

        # ── Build and start ───────────────────────────────────────────────────
        self._build_ui()
        self.refresh_library()   # populate the library with all available modules
        self._set_icon()         # draw the red H window icon

    # ── Window icon ───────────────────────────────────────────────────────────

    def _set_icon(self):
        """Draw a bold red 'H' pixel-by-pixel into a PhotoImage and set it
        as the window icon.  No external image file required."""
        try:
            size = 64
            img  = tk.PhotoImage(width=size, height=size)
            img.put(THEME["bg_dark"], to=(0, 0, size, size))   # dark background
            red = "#c1121f"
            bar_w, cx, top, bot = 10, size // 2, 8, size - 8
            # Left vertical bar of the H
            for x in range(8, 8 + bar_w):
                for y in range(top, bot):
                    img.put(red, to=(x, y, x+1, y+1))
            # Right vertical bar of the H
            for x in range(size - 8 - bar_w, size - 8):
                for y in range(top, bot):
                    img.put(red, to=(x, y, x+1, y+1))
            # Horizontal crossbar of the H
            for x in range(8 + bar_w, size - 8 - bar_w):
                for y in range(cx - 5, cx + 5):
                    img.put(red, to=(x, y, x+1, y+1))
            self.iconphoto(True, img)
        except Exception:
            pass   # non-fatal — some platforms don't support iconphoto

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        """Create the three-pane layout and wire all callbacks.

        Layout:
            TopBar           (full width, fixed height)
            PanedWindow      (fills remaining space)
                LibraryPane  (left  — module cards + search)
                PlanPane     (centre — ordered plan steps)
                DetailPane   (right  — selected module details)
        """
        # Top bar with logo and export/action buttons
        topbar = TopBar(
            self,
            on_new_module       = self._create_new_module,
            on_export_word      = self._export_word,
            on_export_json      = self._export_json,
            on_export_questions = self._export_questions,
            on_clear_plan       = self._clear_plan,
        )
        topbar.pack(fill=tk.X, padx=10, pady=(10, 6))

        # Horizontal splitter — user can drag sashes to resize panes
        paned = tk.PanedWindow(
            self, orient=tk.HORIZONTAL, bg=THEME["bg_dark"],
            sashwidth=5, sashrelief=tk.FLAT, sashpad=0,
        )
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # ── Left pane: module library ─────────────────────────────────────────
        self.library_pane = LibraryPane(
            paned,
            search_var          = self.search_var,
            search_field_var    = self.search_field_var,
            filter_category     = self.filter_category,
            on_card_click       = self._on_lib_click,         # single click → show detail
            on_card_double_click= self._add_to_plan,          # double click  → add to plan
            on_drag_motion      = self._on_drag_motion,       # drag start/move
            on_drag_release     = self._on_drag_release,      # drag drop
            on_set_category     = self._set_category,         # filter tab clicked
            on_set_search_field = self._set_search_field,     # field selector clicked
            on_clear_search     = lambda: self.search_var.set(""),
        )

        # ── Centre pane: active hunt plan ─────────────────────────────────────
        self.plan_pane = PlanPane(
            paned,
            on_card_click = self._show_detail,     # click plan card → show detail
            on_move       = self._move_module,     # ▲ / ▼ buttons
            on_remove     = self._remove_from_plan,# ✕ button
            on_edit       = self._edit_module,     # ✎ button
        )

        # ── Right pane: module details ────────────────────────────────────────
        self.detail_pane = DetailPane(
            paned,
            on_add_to_plan      = self._add_to_plan,
            on_remove_from_plan = self._remove_from_plan,
            on_edit_module      = self._edit_module,
            on_mitre_click      = self._mitre_search,   # left-click MITRE chip
        )

        paned.add(self.library_pane, minsize=290, width=320)
        paned.add(self.plan_pane,    minsize=380, width=570)
        paned.add(self.detail_pane,  minsize=290, width=400)

        # ── Drag-and-drop controller ──────────────────────────────────────────
        # Needs direct references to the plan canvas/inner frame so it can
        # calculate insertion position and render the drop indicator line.
        self.drag = DragController(
            plan_canvas      = self.plan_pane.canvas,
            plan_inner       = self.plan_pane.inner,
            on_drop_callback = self._on_drop,
        )

        # ── Initial scroll binding ────────────────────────────────────────────
        # Bind mousewheel on every widget inside each scrollable pane.
        # This must be called here (after widgets are created) AND again
        # after any refresh that recreates child widgets.
        bind_scroll_recursive(self.library_pane.inner, self.library_pane._canvas)
        bind_scroll_recursive(self.plan_pane.inner,    self.plan_pane.canvas)
        bind_scroll_recursive(self.detail_pane.inner,  self.detail_pane._canvas)

    # ── Search debounce ───────────────────────────────────────────────────────

    def _debounced_refresh(self):
        """Delay the library rebuild by 120 ms after the last keystroke.

        Without debouncing, each character typed triggers a full rebuild of
        all library cards which causes visible lag for large module sets.
        With debouncing, the rebuild only runs once the user pauses typing.
        """
        if self._search_after_id:
            self.after_cancel(self._search_after_id)   # cancel previous timer
        self._search_after_id = self.after(120, self._do_refresh)

    def _do_refresh(self):
        """Execute the deferred library refresh (called by the debounce timer)."""
        self._search_after_id = None
        self.refresh_library()

    # ── Library management ────────────────────────────────────────────────────

    def refresh_library(self):
        """Refilter available modules and redraw the library card list.

        Called after: search query change, category filter change, module
        added/removed from plan, module created/edited.
        """
        # Push current UI state into the search controller
        self.search.set_query(self.search_var.get())
        self.search.set_field(self.search_field_var.get())

        # Filter the full module list
        filtered = self.search.filter(
            self.available_modules, self.filter_category.get()
        )

        # Tell the library pane which modules to show and which are in the plan
        self.library_pane.refresh(filtered, self.plan.get_plan_ids())

        # Keep the drag controller's card position list in sync with the plan pane
        self.drag.set_plan_cards(self.plan_pane.card_widgets)

    def _set_category(self, cat: str):
        """Handle a category filter button click — update state and refresh."""
        self.filter_category.set(cat)
        self.library_pane.highlight_category(cat)   # update button highlight
        self.refresh_library()

    def _set_search_field(self, field: str):
        """Handle a search-field selector click — update state and refresh."""
        self.search_field_var.set(field)
        self.search.set_field(field)
        self.library_pane.highlight_field(field)    # update button highlight
        self.refresh_library()

    def _on_lib_click(self, mod: dict):
        """Handle a single click on a library card — select and show detail."""
        self.selected_module = mod
        self._show_detail(mod)

    # ── Detail pane ───────────────────────────────────────────────────────────

    def _show_detail(self, mod: dict):
        """Show full module details in the right pane.

        Also determines whether the module is currently in the plan so the
        detail pane can render the correct Add / Remove button.
        """
        self.selected_module = mod
        in_plan = self.plan.contains(mod["id"])
        self.detail_pane.show_module(mod, in_plan)

    # ── Plan mutations ────────────────────────────────────────────────────────

    def _add_to_plan(self, mod: dict):
        """Add a module to the end of the plan (from library double-click or button)."""
        ok = self.plan.add(mod)
        if ok:
            self._refresh_all(mod)

    def _on_drop(self, mod: dict, insert_idx: int):
        """Handle a completed drag-and-drop from library to plan at *insert_idx*."""
        ok = self.plan.add(mod, insert_idx)
        if ok:
            self._refresh_all(mod)

    def _remove_from_plan(self, mod: dict):
        """Remove a module from the plan (✕ button or Remove button in detail pane)."""
        self.plan.remove(mod["id"])
        self._refresh_all()
        # If this was the selected module, clear the detail pane
        if self.selected_module and self.selected_module["id"] == mod["id"]:
            self.detail_pane.show_empty()

    def _move_module(self, mod: dict, direction: int):
        """Shift a plan module up (-1) or down (+1) in the ordered list."""
        if self.plan.move(mod["id"], direction):
            # Only need to redraw the plan pane — library and detail are unaffected
            self.plan_pane.refresh(self.plan.modules)
            self.drag.set_plan_cards(self.plan_pane.card_widgets)

    def _refresh_all(self, mod: dict | None = None):
        """Redraw both the plan pane and library, then optionally refresh detail.

        Called after any plan mutation (add, remove, edit) to keep all
        three panes consistent.
        """
        self.plan_pane.refresh(self.plan.modules)
        self.drag.set_plan_cards(self.plan_pane.card_widgets)
        self.refresh_library()
        if mod is not None:
            self._show_detail(mod)   # re-render detail with updated in_plan state

    # ── Drag-and-drop glue ────────────────────────────────────────────────────

    def _on_drag_motion(self, event: tk.Event, mod: dict):
        """Relay drag-motion events from library cards to the drag controller."""
        self.drag.set_plan_cards(self.plan_pane.card_widgets)
        self.drag.on_motion(event, mod)

    def _on_drag_release(self, event: tk.Event, mod: dict):
        """Relay drag-release events from library cards to the drag controller."""
        self.drag.on_release(event, mod)

    # ── Module create / edit ──────────────────────────────────────────────────

    def _create_new_module(self):
        """Open the editor dialog to create a brand-new module."""
        ModuleEditorDialog(self, callback=self._on_module_created)

    def _edit_module(self, mod: dict):
        """Open the editor dialog pre-populated with an existing module's data.

        We look up the live entry in available_modules (rather than using
        the plan copy) so edits always operate on the canonical version.
        """
        live = next(
            (m for m in self.available_modules if m["id"] == mod["id"]), mod
        )
        ModuleEditorDialog(self, callback=self._on_module_edited, existing=live)

    def _on_module_created(self, mod: dict):
        """Callback from editor dialog when a new module is saved."""
        save_module_to_disk(mod)         # persist to disk
        cache_search_fields(mod)         # compute _search_* fields
        self.available_modules.append(mod)
        self.refresh_library()
        self._show_detail(mod)           # auto-select the new module

    def _on_module_edited(self, mod: dict):
        """Callback from editor dialog when an existing module is updated."""
        save_module_to_disk(mod)
        cache_search_fields(mod)

        # Update the available_modules list in place
        for i, m in enumerate(self.available_modules):
            if m["id"] == mod["id"]:
                self.available_modules[i] = mod
                break

        # Update the plan copy if this module is in the plan
        self.plan.update_module(mod)

        self._refresh_all(mod)

    # ── MITRE chip search ─────────────────────────────────────────────────────

    def _mitre_search(self, code: str):
        """Handle left-click on a MITRE chip in the detail pane.

        Switches the search field to 'MITRE' and appends the clicked
        technique code to the search bar using + (AND) logic.  Multiple
        chips can be clicked to accumulate an AND filter.
        Clearing the search bar resets the filter.
        """
        self._set_search_field("MITRE")
        current = self.search_var.get().strip()
        if not current:
            # First chip clicked — set it as the sole query
            self.search_var.set(code.lower())
        else:
            # Append with AND (+) if not already present
            terms = [t.strip() for t in current.split("+")]
            if code.lower() not in terms:
                self.search_var.set(current + " + " + code.lower())
        self.library_pane.scroll_to_top()

    # ── Export ────────────────────────────────────────────────────────────────

    def _guard_empty(self) -> bool:
        """Show a warning and return True if the plan is empty.

        Used as a guard at the start of every export method.
        """
        from tkinter import messagebox
        if not self.plan.modules:
            messagebox.showwarning(
                "Empty Plan", "Add modules to your plan before exporting."
            )
            return True
        return False

    def _export_json(self):
        """Export the current plan as a JSON file."""
        if self._guard_empty():
            return
        ExportController.export_json(self.plan.build_export_dict())

    def _export_questions(self):
        """Export all questionnaire items from the plan as a plain-text file."""
        if self._guard_empty():
            return
        ExportController.export_questionnaire(self.plan.modules)

    def _export_word(self):
        """Export the plan as a formatted Word (.docx) document via Node.js."""
        if self._guard_empty():
            return
        ExportController.export_word(
            self,                          # parent window for dialogs
            self.plan.build_export_dict(), # serialised plan data
            self._script_dir,              # project root (where export_docx.js lives)
        )

    def _clear_plan(self):
        """Remove all modules from the plan after user confirmation."""
        from tkinter import messagebox
        if not self.plan.modules:
            return
        if messagebox.askyesno("Clear Plan",
                               "Remove all modules from the hunt plan?"):
            self.plan.clear()
            self._refresh_all()
            self.detail_pane.show_empty()
