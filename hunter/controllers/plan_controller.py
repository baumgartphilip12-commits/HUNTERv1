"""
hunter/controllers/plan_controller.py
======================================
Owns the ordered list of modules that make up the active hunt plan and
provides all mutations to that list.

Design notes
------------
- The controller holds *copies* of module dicts (via ``deepcopy``) so that
  edits to a plan module do not silently affect the library entry and vice
  versa.
- Each copy is given a ``plan_uid`` — a short random string — so that if
  the same module template were ever added twice (currently blocked), the
  two instances could still be distinguished.
- All user-facing confirmation dialogs (duplicate detection) live here
  because they are part of the mutation logic, not the view.
"""

from copy import deepcopy
from datetime import datetime
import uuid
from tkinter import messagebox


class PlanController:
    """Manages the ordered list of modules that form the active hunt plan.

    Attributes
    ----------
    modules : list[dict]
        Ordered list of module dicts currently in the plan.
        Index 0 is Step 1, index 1 is Step 2, etc.
    """

    def __init__(self):
        self.modules: list[dict] = []

    # ── Read-only helpers ─────────────────────────────────────────────────────

    def contains(self, mod_id: str) -> bool:
        """Return True if a module with this id is already in the plan."""
        return any(m["id"] == mod_id for m in self.modules)

    def get_plan_ids(self) -> set[str]:
        """Return the set of module IDs currently in the plan.
        Used by LibraryPane to render the green ✓ badge on in-plan cards."""
        return {m["id"] for m in self.modules}

    def total_steps(self) -> int:
        """Total number of individual action steps across all plan modules."""
        return sum(
            len(g["actions"])
            for m in self.modules
            for g in m.get("hunt_actions", [])
        )

    def total_questions(self) -> int:
        """Total number of questionnaire items across all plan modules."""
        return sum(len(m.get("questions", [])) for m in self.modules)

    # ── Mutations ─────────────────────────────────────────────────────────────

    def add(self, mod: dict, insert_idx: int | None = None) -> bool:
        """Add a module to the plan at *insert_idx* (or append if None).

        Checks performed before adding:
        1. Exact duplicate — same module already in the plan (blocked, no dialog).
        2. Action-group title conflict — another module has a group with the same
           title.  User is warned and may choose to add anyway.

        Returns True if the module was added, False if the user cancelled or
        the module was already present.
        """
        # Guard: do not allow the same module twice
        if self.contains(mod["id"]):
            messagebox.showinfo(
                "Already in Plan",
                f"'{mod['name']}' is already in your hunt plan."
            )
            return False

        # Warn about action-group title collisions (non-blocking)
        conflicts = self._find_title_conflicts(mod)
        if conflicts:
            if not messagebox.askyesno(
                "Duplicate Action Groups",
                "Some action group titles already exist in your plan:\n\n"
                + "\n".join(f"  • {c}" for c in conflicts)
                + "\n\nAdd anyway?"
            ):
                return False

        # Deep-copy so the plan instance is independent of the library entry
        instance = deepcopy(mod)
        instance["plan_uid"] = str(uuid.uuid4())[:8]   # short unique plan ID

        if insert_idx is None or insert_idx >= len(self.modules):
            self.modules.append(instance)
        else:
            self.modules.insert(insert_idx, instance)
        return True

    def remove(self, mod_id: str) -> None:
        """Remove the module with *mod_id* from the plan."""
        self.modules = [m for m in self.modules if m["id"] != mod_id]

    def move(self, mod_id: str, direction: int) -> bool:
        """Shift a module up (direction=-1) or down (direction=+1) by one step.

        Returns True if the move was performed, False if the module was not
        found or is already at the boundary.
        """
        idx = next(
            (i for i, m in enumerate(self.modules) if m["id"] == mod_id), None
        )
        if idx is None:
            return False
        new_idx = idx + direction
        if not (0 <= new_idx < len(self.modules)):
            return False   # already at top or bottom
        self.modules.insert(new_idx, self.modules.pop(idx))
        return True

    def update_module(self, mod: dict) -> None:
        """Replace the plan entry for *mod* with an updated version after editing.

        The ``plan_uid`` from the original entry is preserved so the plan
        position is maintained.
        """
        for i, m in enumerate(self.modules):
            if m["id"] == mod["id"]:
                updated = deepcopy(mod)
                updated["plan_uid"] = m.get("plan_uid", str(uuid.uuid4())[:8])
                self.modules[i] = updated
                return

    def clear(self) -> None:
        """Remove all modules from the plan."""
        self.modules.clear()

    # ── Export ────────────────────────────────────────────────────────────────

    def build_export_dict(self) -> dict:
        """Build a serialisable dict representing the current plan.

        This is the JSON structure consumed by export_docx.js and also
        written directly for the JSON export.
        """
        return {
            "generated":          datetime.now().isoformat(),
            "total_modules":      len(self.modules),
            "total_hunt_actions": self.total_steps(),
            "total_questions":    self.total_questions(),
            "modules": [
                {
                    "step":             step_num,
                    "name":             m["name"],
                    "category":         m.get("category"),
                    "priority":         m.get("priority"),
                    "author":           m.get("author"),
                    "last_updated":     m.get("last_updated"),
                    "estimated_hours":  m.get("estimated_hours", 0),
                    "mitre_techniques": m.get("mitre_techniques", []),
                    "prerequisites":    m.get("prerequisites", []),
                    "required_tools":   m.get("required_tools", []),
                    "tags":             m.get("tags", []),
                    "hunt_actions":     m.get("hunt_actions", []),
                    "questions":        m.get("questions", []),
                    "references":       m.get("references", []),
                }
                for step_num, m in enumerate(self.modules, 1)
            ],
        }

    # ── Private ───────────────────────────────────────────────────────────────

    def _find_title_conflicts(self, mod: dict) -> list[str]:
        """Return action-group titles in *mod* that already exist in the plan."""
        existing_titles = {
            g["title"]
            for m in self.modules
            for g in m.get("hunt_actions", [])
        }
        return [
            g["title"]
            for g in mod.get("hunt_actions", [])
            if g["title"] in existing_titles
        ]
