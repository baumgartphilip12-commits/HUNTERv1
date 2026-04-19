"""
hunter/models/module_store.py
==============================
Responsible for all module persistence — reading from and writing to the
``modules/`` directory on disk.

Module file format
------------------
Each module is a single ``.json`` file named after its ``id`` field,
e.g. ``mod_aws_general.json``.  The schema is:

    {
      "id":               str,          # unique identifier, used as filename
      "name":             str,          # display name shown in the UI
      "category":         str,          # one of CATEGORIES from theme.py
      "author":           str,
      "last_updated":     str,          # YYYY-MM-DD
      "priority":         str,          # one of PRIORITIES from theme.py
      "estimated_hours":  int,
      "mitre_techniques": [str],        # list of ATT&CK technique IDs
      "prerequisites":    [str],
      "required_tools":   [str],
      "tags":             [str],
      "references":       [str],
      "hunt_actions": [
        {
          "title":   str,
          "actions": [str]              # individual numbered steps
        }
      ],
      "questions": [str]                # pre-engagement questionnaire items
    }

Private runtime fields (prefixed ``_``) are added in memory but never
written to disk:
    _filepath       – absolute path to the JSON file on disk
    _search_*       – pre-lowercased search strings for fast filtering
"""

import json
import os
import uuid


def get_modules_dir() -> str:
    """Return the absolute path to the ``modules/`` directory.

    Directory layout::

        project_root/          ← main.py lives here
            modules/           ← JSON files live here
            hunter/            ← Python package
                models/
                    module_store.py   ← this file

    We walk upward two levels from this file to reach the project root.
    """
    this_file   = os.path.abspath(__file__)           # hunter/models/module_store.py
    models_dir  = os.path.dirname(this_file)          # hunter/models/
    package_dir = os.path.dirname(models_dir)         # hunter/
    project_dir = os.path.dirname(package_dir)        # project root
    return os.path.join(project_dir, "modules")


def cache_search_fields(mod: dict) -> dict:
    """Pre-compute lowercased search strings and store them on the module dict.

    Called once when a module is first loaded (or saved/edited).  During
    library filtering, these cached values are used directly instead of
    calling ``.lower()`` on every module field for every keystroke.

    The cached keys all start with ``_search_`` and are stripped before
    any disk write (see ``save_module_to_disk``).
    """
    mod["_search_name"]   = mod.get("name", "").lower()
    mod["_search_author"] = mod.get("author", "").lower()
    mod["_search_cat"]    = mod.get("category", "").lower()
    mod["_search_prio"]   = mod.get("priority", "").lower()
    # List fields — pre-lower each element
    mod["_search_tags"]   = [t.lower() for t in mod.get("tags", [])]
    mod["_search_mitre"]  = [t.lower() for t in mod.get("mitre_techniques", [])]
    mod["_search_titles"] = [g.get("title", "").lower()
                              for g in mod.get("hunt_actions", [])]
    return mod


def load_modules_from_disk() -> list[dict]:
    """Read every ``.json`` file from the modules directory.

    Files are sorted alphabetically so the library order is deterministic.
    Any file that fails to parse is skipped with a console warning.

    Returns a list of module dicts, each augmented with ``_filepath``
    and the ``_search_*`` cached fields.
    """
    mdir = get_modules_dir()
    os.makedirs(mdir, exist_ok=True)   # create modules/ if it doesn't exist yet
    modules: list[dict] = []

    for fname in sorted(os.listdir(mdir)):
        if not fname.endswith(".json"):
            continue                        # ignore non-JSON files
        fpath = os.path.join(mdir, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                mod = json.load(f)
            mod["_filepath"] = fpath        # remember where this module lives
            cache_search_fields(mod)        # pre-compute lowercase search fields
            modules.append(mod)
        except Exception as exc:
            # Bad JSON or permission error — warn and continue loading others
            print(f"[WARN] Could not load module {fname}: {exc}")

    return modules


def save_module_to_disk(mod: dict) -> str:
    """Write *mod* to its ``.json`` file, creating it if it does not exist.

    Private runtime fields (keys beginning with ``_``) are stripped so they
    are never persisted.  The filename is derived from ``mod["id"]``.

    Returns the absolute path of the file written.
    """
    mdir = get_modules_dir()
    os.makedirs(mdir, exist_ok=True)

    fname = mod.get("id", "mod_" + uuid.uuid4().hex[:8]) + ".json"
    fpath = os.path.join(mdir, fname)

    # Strip all runtime-only private fields before writing
    save_data = {k: v for k, v in mod.items() if not k.startswith("_")}

    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(save_data, f, indent=2)

    mod["_filepath"] = fpath   # update in-memory reference to the new path
    return fpath
