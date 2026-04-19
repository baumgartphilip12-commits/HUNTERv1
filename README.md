# HUNTER — Threat Hunt Plan Builder
### Base Documentation  |  Version 1.0  |  April 2026

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Quick Start](#2-quick-start)
3. [Project Structure](#3-project-structure)
4. [Architecture](#4-architecture)
5. [Module System](#5-module-system)
6. [User Interface Guide](#7-user-interface-guide)
7. [Search Reference](#8-search-reference)
8. [Export Formats](#9-export-formats)
9. [Creating and Editing Modules](#10-creating-and-editing-modules)
10. [Code Reference](#11-code-reference)
11. [Dependencies](#12-dependencies)
12. [Troubleshooting](#13-troubleshooting)

---

## 1. Project Overview

HUNTER is a desktop application built for cybersecurity threat hunters that
provides a visual, modular interface for building threat hunt plans and
generating mission partner questionnaires.

### What it does

- Maintains a **library of hunt modules** — each module represents a specific
  technology or threat actor and contains a set of hunt action groups, individual
  hunt steps with exact commands or navigation paths, pre-engagement questionnaire
  items, MITRE ATT&CK technique mappings, prerequisites, and required tools.

- Allows the analyst to **assemble a hunt plan** by dragging or double-clicking
  modules into the centre pane, ordering them, and reordering them freely.

- **Exports the plan** in three formats:
  - Professional Word document (`.docx`) with cover page, exec summary, and
    formatted questionnaire tables.
  - Machine-readable JSON for integration with other tooling.
  - Plain-text questionnaire file for mission partner distribution.

### Design goals

| Goal | Implementation |
|---|---|
| No external Python dependencies | Standard library only (`tkinter`, `json`, `subprocess`, `threading`, etc.) |
| Modules are human-editable files | Each module is a standalone `.json` file in `modules/` |
| Easily extensible | Add a new `.json` file to `modules/` — it appears in the library on next launch |
| Clean separation of concerns | MVC-style split: models, views, controllers |
| Fast search across all fields | Pre-cached lowercase fields, debounced 120 ms rebuild |

---

## 2. Quick Start

### Requirements

| Requirement | Version | Purpose |
|---|---|---|
| Python | 3.11+ | Running the application |
| Node.js | 18+ | Word (.docx) export only |

> Python is the **only** requirement to run the application. Node.js is only
> needed if you use **Export Word**. On first use, HUNTER will offer to install
> the required `docx` npm package automatically.

### Running the application

```
python main.py
```

That is the only command needed. The application reads modules from the
`modules/` directory automatically on startup.

### Project folder layout (what you need)

```
YourProject/
├── main.py                  ← Entry point — run this
├── export_docx.js           ← Word export script (requires Node.js)
├── modules/                 ← Hunt module JSON files
│   ├── mod_aws_general.json
│   ├── mod_keycloak.json
│   └── ...
└── hunter/                  ← Python package (do not move)
    ├── app.py
    ├── theme.py
    ├── scroll.py
    ├── models/
    ├── views/
    └── controllers/
```

---

## 3. Project Structure

### Full file tree

```
YourProject/
│
├── main.py                              Entry point; DPI setup; launches HunterApp
├── export_docx.js                       Node.js Word document generator
│
├── modules/                             Hunt module JSON files (one per module)
│   └── mod_<name>.json
│
└── hunter/                              Python application package
    │
    ├── __init__.py                      Package marker (empty)
    ├── app.py                           Root Tk window; wires all controllers + views
    ├── theme.py                         All colours, fonts, and UI constants
    ├── scroll.py                        Mousewheel binding utilities
    │
    ├── models/
    │   ├── __init__.py
    │   └── module_store.py              Load / save / cache modules from disk
    │
    ├── controllers/
    │   ├── __init__.py
    │   ├── plan_controller.py           Plan list state: add / remove / move / export
    │   ├── search_controller.py         Search query state and boolean filter logic
    │   ├── drag_controller.py           Drag-and-drop ghost window and indicator line
    │   └── export_controller.py         JSON / Word / questionnaire export
    │
    └── views/
        ├── __init__.py
        ├── topbar.py                    Header bar: logo + action buttons
        ├── library_pane.py              Left pane: module cards, search, category filter
        ├── plan_pane.py                 Centre pane: ordered plan steps
        ├── detail_pane.py               Right pane: full module detail + MITRE chips
        └── editor_dialog.py             Modal dialog: create / edit a module
```

---

## 4. Architecture

HUNTER uses a **passive-view MVC** pattern adapted for tkinter.

```
┌─────────────────────────────────────────────────────────┐
│                        main.py                          │
│   Warning suppression · DPI awareness · app.mainloop()  │
└────────────────────────┬────────────────────────────────┘
                         │ instantiates
                         ▼
┌─────────────────────────────────────────────────────────┐
│                      HunterApp                          │
│   (hunter/app.py)                                       │
│                                                         │
│   The ONLY file that imports from both controllers and  │
│   views.  Connects them via callback arguments.         │
│   Implements all mutation methods (_add_to_plan, etc.)  │
└──┬───────────────┬───────────────┬──────────────────────┘
   │               │               │
   ▼               ▼               ▼
Controllers      Views          Models
────────────     ─────────      ──────────────
PlanController   TopBar         module_store.py
SearchController LibraryPane    (load/save JSON)
DragController   PlanPane
ExportController DetailPane
                 EditorDialog
```

### Data flow

```
User types in search bar
        │
        ▼
search_var (StringVar) fires trace callback
        │
        ▼
HunterApp._debounced_refresh()  ← 120 ms timer
        │
        ▼
HunterApp.refresh_library()
        │
        ├─ SearchController.filter(available_modules, category)
        │       └─ SearchController._module_matches(mod)
        │               └─ Uses pre-cached _search_* fields
        │
        └─ LibraryPane.refresh(filtered_modules, plan_ids)
                └─ Redraws all card widgets
                └─ bind_scroll_recursive() on new widgets
```

### Why callbacks instead of direct imports?

Views are given callback functions at construction time. They never
`import PlanController` — they just call `self._on_add(mod)`. This means:

- Any view can be tested or replaced independently.
- `app.py` is the single, readable place where all interactions are defined.
- Controllers have no tkinter imports and can be unit tested without a display.

---

## 5. Module System

### What is a module?

A module is a JSON file that describes how to hunt for threats on a specific
technology, platform, or threat actor. Each module contains:

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique identifier; also used as the filename |
| `name` | string | Display name shown in the library and plan |
| `category` | string | One of: Cloud, Identity, Endpoint, Network, APT, Other |
| `author` | string | Who created or last revised this module |
| `last_updated` | string | Date in `YYYY-MM-DD` format |
| `priority` | string | Critical / High / Medium / Low |
| `estimated_hours` | integer | Approximate time to execute this module |
| `mitre_techniques` | array of strings | ATT&CK technique IDs, e.g. `["T1078", "T1059.001"]` |
| `prerequisites` | array of strings | What must be in place before hunting |
| `required_tools` | array of strings | Tools needed to execute hunt steps |
| `tags` | array of strings | Free-form labels for search and categorisation |
| `references` | array of strings | URLs to relevant documentation or threat intel |
| `hunt_actions` | array of objects | Ordered list of action groups (see below) |
| `questions` | array of strings | Pre-engagement questionnaire items |

### Hunt action group format

Each entry in `hunt_actions` is an object with:

```json
{
  "title": "Credential Abuse Detection",
  "actions": [
    "Run: aws iam generate-credential-report ...",
    "Query CloudTrail via Athena: SELECT ...",
    "Splunk SPL: index=cloudtrail eventName=AssumeRole ..."
  ]
}
```

- **title** — The objective name, shown as a group header in the UI and exported document.
- **actions** — Individual numbered steps. Each step should include the exact
  command, query, or navigation path to follow. Be as specific as possible —
  include tool names, flags, expected output patterns, and thresholds.

### Adding a new module

1. Create a new file in `modules/` named `mod_<descriptive_name>.json`.
2. Fill in all required fields following the schema above.
3. Restart HUNTER (or it will appear on next launch automatically).

Alternatively, use the **＋ New Module** button in the application to create
a module through the editor dialog — it will be saved to `modules/`
automatically.

### Module categories and visual treatment

| Category | Icon | Special styling |
|---|---|---|
| Cloud | ☁ | Standard styling |
| Identity | 🔑 | Standard styling |
| Endpoint | 💻 | Standard styling |
| Network | 🌐 | Standard styling |
| APT | 🎯 | **Red tint** — visually distinct to signal nation-state threat actor content |
| Other | 🔍 | Standard styling |

---

## 6. User Interface Guide

### Three-pane layout

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  H HUNTER  THREAT HUNT PLAN BUILDER  — Modular Hunt Planning   [buttons]    │
├─────────────────┬───────────────────────────────┬────────────────────────────┤
│  MODULE LIBRARY │        HUNT PLAN              │   MODULE DETAILS           │
│                 │                               │                            │
│  ⌕ [search] ✕  │  0 modules · 0 steps · 0 Qs  │  (select a module to view) │
│  All Cloud...   │                               │                            │
│                 │  ┌─────────────────────────┐  │                            │
│  ┌───────────┐  │  │ Step 1  AWS Hunt        │  │                            │
│  │ AWS Hunt  │  │  │ ▲ ▼ ✎ ✕                │  │                            │
│  │ High · 4h │  │  └─────────────────────────┘  │                            │
│  └───────────┘  │                               │                            │
│  ┌───────────┐  │  ← drag modules here          │                            │
│  │ Keycloak  │  │     or double-click           │                            │
│  └───────────┘  │     in the library            │                            │
└─────────────────┴───────────────────────────────┴────────────────────────────┘
```

### Left pane — Module Library

| Element | Function |
|---|---|
| Search bar | Filter modules by text query (see Search Reference) |
| ✕ button | Clear the search bar |
| Field selector | `All Fields / Name / Tags / MITRE` — scope the search |
| Category tabs | `All / Cloud / Identity / Endpoint / Network / APT / Other` |
| Module card | Single-click: show details. Double-click: add to plan. Drag: drop into plan at specific position. |
| ✓ badge | Shown on cards that are already in the plan |
| Priority stripe | Coloured left edge — red = Critical, orange = High, amber = Medium, green = Low |

### Centre pane — Hunt Plan

| Element | Function |
|---|---|
| Step number badge | Colour-coded by priority; shows execution order |
| ▲ / ▼ buttons | Move module up or down in the plan |
| ✎ button | Open the editor to modify this module |
| ✕ button | Remove module from the plan |
| Clicking the card | Shows this module's full details in the right pane |
| Drag indicator | Blue horizontal line shows where a dragged module will be dropped |

### Right pane — Module Details

| Section | Description |
|---|---|
| Header card | Module name, priority, category, estimated hours, tags |
| MITRE ATT&CK | Clickable chips — **left-click** adds to search filter; **right-click** opens the ATT&CK website |
| Prerequisites | What must be in place before the hunt can safely run |
| Required Tools | Software and access needed to execute the module |
| Hunt Actions | Each group and its numbered steps with exact commands |
| Questionnaire Items | The pre-engagement questions this module contributes |
| References | Links to threat intel, vendor documentation, CVEs |
| ✎ Edit Module | Open the editor for this module |
| ＋ Add to Hunt Plan | Add to the plan (if not already present) |
| ✕ Remove from Plan | Remove from the plan (if currently present) |

### Top bar buttons

| Button | Action |
|---|---|
| ＋ New Module | Open the editor dialog to create a new module from scratch |
| ⬇ Export Word | Export the plan as a formatted `.docx` Word document |
| ⬇ Export JSON | Export the plan as a machine-readable JSON file |
| ⬇ Export Questions | Export all questionnaire items as a plain-text file |
| 🗑 Clear Plan | Remove all modules from the plan (with confirmation) |

---

## 7. Search Reference

The search bar accepts a simple boolean query language.

### Operators

| Operator | Meaning | Example |
|---|---|---|
| *(word)* | Substring match | `keycloak` |
| `A + B` | AND — must match both | `T1078 + cloud` |
| `A \| B` | OR — must match either | `apt33 \| apt34` |
| `-word` | NOT — exclude matches | `endpoint + -windows` |

### Precedence

OR (`|`) is evaluated first, splitting the query into OR-groups.
Within each OR-group, AND (`+`) is evaluated left to right.
NOT (`-`) applies to a single AND term.

### Field selector

| Field | What is searched |
|---|---|
| All Fields | Name, tags, MITRE IDs, author, category, priority, action group titles |
| Name | Module name only |
| Tags | Tags list only |
| MITRE | MITRE technique IDs (partial match supported: `T1059` matches `T1059.001`) |

### MITRE chip clicking (in detail pane)

- **Left-click** a MITRE chip → switches field to `MITRE` and appends the code
  to the search bar using AND (`+`) logic. Click multiple chips to accumulate
  a multi-technique filter. Clear the search bar to reset.
- **Right-click** a MITRE chip → opens `https://attack.mitre.org/techniques/<ID>/`
  in your default browser.

### Examples

```
aws                         All modules mentioning "aws"
T1078                       All modules with technique T1078
T1059 + endpoint            Endpoint modules covering T1059
apt33 | apt34               Either APT33 or APT34 modules
cloud + -kubernetes         Cloud modules that are not Kubernetes
```

---

## 8. Export Formats

### Word Document (`.docx`)

**Requires:** Node.js 18+ installed on the system. The `docx` npm package
is installed automatically on first use (one-time, ~5 MB download).

The Word document includes:

1. **Cover page** — HUNTER branding, generation date, totals summary
2. **Table of Contents** — page references for all sections
3. **Executive Summary** — module count, step count, question count, total estimated hours, full MITRE ATT&CK coverage list, module execution order
4. **One section per module** — metadata table, MITRE techniques, prerequisites, required tools, all action groups with numbered steps in monospace font, references
5. **Pre-Hunt Questionnaire** — all questions formatted as fill-in tables with question number badges and answer/notes rows

The document uses US Letter page size, Arial body font, Courier New for
commands and queries, and a dark-navy / cyan colour scheme.

### JSON Plan File (`.json`)

A machine-readable snapshot of the current plan. Useful for version control,
integration with SIEM or ticketing systems, or loading into other tools.

Structure:
```json
{
  "generated": "2026-04-15T20:00:00",
  "total_modules": 3,
  "total_hunt_actions": 33,
  "total_questions": 24,
  "modules": [
    {
      "step": 1,
      "name": "AWS General Hunt",
      "category": "Cloud",
      "priority": "High",
      ...
      "hunt_actions": [...],
      "questions": [...]
    }
  ]
}
```

### Plain-Text Questionnaire (`.txt`)

A formatted text file containing all questionnaire items from the plan,
grouped by module. Each question has:
- A sequential `Q##` number
- An answer line
- A notes / evidence line

Intended to be distributed to the mission partner before the hunt engagement.

---

## 9. Creating and Editing Modules

### Using the editor dialog

Click **＋ New Module** (top bar) or **✎ Edit Module** (detail pane or plan card).

| Field | Type | Notes |
|---|---|---|
| Module Name | Text | Required. Used as the display name everywhere. |
| Category | Dropdown | Cloud / Identity / Endpoint / Network / APT / Other |
| Author | Text | Name or team responsible for this module |
| Priority | Dropdown | Critical / High / Medium / Low |
| Est. Hours | Number | Integer estimate of execution time |
| MITRE Techniques | Text | Comma-separated IDs, e.g. `T1078, T1059.001` |
| Prerequisites | Text | Comma-separated list |
| Required Tools | Text | Comma-separated list |
| Tags | Text | Comma-separated keywords for search |
| References | Text | Comma-separated URLs |
| Hunt Action Groups | Grouped inputs | Each group has a title and one or more step entries |
| Questionnaire Items | Text entries | One question per entry box |

#### Action groups

Each **action group** represents one hunt objective (e.g. "Credential Abuse
Detection"). Inside the group, add individual **steps** using the
**＋ Add Step** button. Each step should be a specific, executable action
with an exact command, query, or navigation path.

Use **＋ Add Action Group** to add multiple objectives to a single module.

### Editing the JSON directly

Module files can also be edited directly in any text editor. The file is
located at `modules/<module_id>.json`. Changes take effect on next
application launch.

Be sure to keep the `id` field in the JSON matching the filename
(without the `.json` extension).

---

## 10. Code Reference

### hunter/app.py — HunterApp

The root `tk.Tk` subclass. The only file that imports from both controllers
and views. All user-interaction callbacks are implemented here.

**Key methods:**

| Method | Triggered by | Action |
|---|---|---|
| `refresh_library()` | Search change, plan change, module edit | Refilters and redraws the library |
| `_add_to_plan(mod)` | Double-click / Add button | Delegates to PlanController, then refreshes |
| `_remove_from_plan(mod)` | ✕ button / Remove button | Removes from plan, refreshes |
| `_move_module(mod, dir)` | ▲ / ▼ buttons | Reorders plan, refreshes plan pane |
| `_show_detail(mod)` | Any card click | Calls DetailPane.show_module() |
| `_mitre_search(code)` | MITRE chip left-click | Appends code to search, switches to MITRE field |
| `_export_word()` | Export Word button | Calls ExportController.export_word() |

### hunter/controllers/plan_controller.py — PlanController

Owns `self.modules: list[dict]` — the ordered plan list.

| Method | Returns | Description |
|---|---|---|
| `add(mod, insert_idx)` | bool | Add module; check duplicate + conflict |
| `remove(mod_id)` | None | Remove by ID |
| `move(mod_id, direction)` | bool | Shift ±1; returns False at boundary |
| `update_module(mod)` | None | Replace after edit, preserve plan_uid |
| `build_export_dict()` | dict | Serialisable plan for export |
| `total_steps()` | int | Sum of all action steps |
| `total_questions()` | int | Sum of all question items |

### hunter/controllers/search_controller.py — SearchController

| Method | Description |
|---|---|
| `set_query(q)` | Lowercase and store query string |
| `set_field(field)` | Set active search field |
| `filter(modules, category)` | Return filtered module list |

### hunter/controllers/export_controller.py — ExportController

All methods are `@staticmethod` or `@classmethod` — no instance state.

| Method | Description |
|---|---|
| `export_json(plan_dict)` | Write JSON to user-chosen path |
| `export_questionnaire(modules)` | Write plain-text questionnaire |
| `export_word(parent, plan_dict, script_dir)` | Full Word export pipeline |
| `find_node()` | Locate node executable on PATH / Windows paths |
| `find_npm(node_cmd)` | Return `{cmd, shell}` for npm install |
| `run_npm_install(parent, dir, node)` | Threaded install with progress dialog |

### hunter/models/module_store.py

| Function | Description |
|---|---|
| `load_modules_from_disk()` | Read all `.json` from `modules/`, cache search fields |
| `save_module_to_disk(mod)` | Write module to `modules/<id>.json` |
| `cache_search_fields(mod)` | Populate `_search_*` keys on a module dict |
| `get_modules_dir()` | Return absolute path to `modules/` directory |

### hunter/scroll.py

| Function | Description |
|---|---|
| `bind_scroll_recursive(widget, canvas)` | Recursively bind mousewheel on all descendants |
| `rebind_scroll(widget, canvas)` | Alias — same full recursive bind, used after refresh |

### hunter/theme.py

Constants only — no functions. Import and use directly:
```python
from hunter.theme import THEME, PRIORITY_COLORS, CATEGORY_ICONS
color = THEME["accent"]          # "#00b4d8"
badge = PRIORITY_COLORS["High"]  # "#e76f51"
icon  = CATEGORY_ICONS["APT"]    # "🎯"
```

---

## 11. Dependencies

### Python (standard library only — no pip installs required)

| Module | Used for |
|---|---|
| `tkinter` | All UI widgets, windows, dialogs |
| `json` | Reading/writing module files and export data |
| `os`, `os.path` | File system paths |
| `subprocess` | Spawning Node.js for Word export; running npm |
| `threading` | Non-blocking npm install (keeps UI responsive) |
| `shutil` | `shutil.which()` for locating node/npm executables |
| `copy.deepcopy` | Isolating plan module copies from library entries |
| `datetime` | Timestamps in exports and module last_updated field |
| `uuid` | Generating unique module IDs and plan_uid values |
| `webbrowser` | Opening ATT&CK website on MITRE chip right-click |
| `warnings` | Suppressing tkinter deprecation/resource warnings |
| `ctypes` | Windows DPI awareness declaration |

### Node.js (Word export only)

| Package | Version | Purpose |
|---|---|---|
| `docx` | 9.x | Generates the `.docx` Word file |

Install manually if needed:
```
npm install docx
```
Run this command in the same directory as `main.py`.

---

## 12. Troubleshooting

### Application won't start

**Symptom:** `ModuleNotFoundError: No module named 'hunter'`

**Cause:** Running Python from the wrong directory.

**Fix:** Always run from the project root (the folder containing `main.py`):
```
cd C:\Users\you\Desktop\Work\Project
python main.py
```

---

### No modules appear in the library

**Symptom:** Library shows "0 modules" with no cards.

**Cause:** The `modules/` directory is missing or in the wrong location.

**Fix:** The `modules/` folder must be in the same directory as `main.py`.
Check `hunter/models/module_store.py` → `get_modules_dir()` to see the
resolved path if needed.

---

### Word export fails with "export_docx.js not found"

**Cause:** `export_docx.js` is missing or is not in the project root.

**Fix:** Ensure `export_docx.js` is in the same folder as `main.py`.

---

### Word export fails with "Node.js Not Found"

**Cause:** Node.js is not installed or not on the system PATH.

**Fix:**
1. Download and install Node.js from https://nodejs.org (LTS version recommended).
2. Restart your terminal and HUNTER after installation.
3. Verify with: `node --version`

---

### Word export fails with "npm Install Failed"

**Cause:** Automatic `npm install docx` failed (network issue, permissions, etc.)

**Fix:** Open a Command Prompt or PowerShell in the project folder and run:
```
npm install docx
```
Then try Export Word again. The `node_modules/` folder must be created
in the same directory as `main.py`.

---

### Mousewheel doesn't scroll in a pane

**Cause:** Focus is on a widget that doesn't have a scroll binding.

**Fix:** This should not occur in the current build. If it does after a Python
upgrade, the fix is in `hunter/scroll.py` → `bind_scroll_recursive()` which
attaches scroll handlers to every widget in each pane including the canvas.

---

### Exported Word document won't open in Microsoft Word

**Cause:** Structural XML errors in the generated document.

**Known good configuration:** Node.js 18+, docx npm package version 9.x.

**Fix:** Delete the `node_modules/` folder and re-run `npm install docx`
to get a fresh install of the package. Then try the export again.

---

### IDE shows 200+ type warnings (PyCharm, etc.)

**Cause:** tkinter's type stubs are incomplete and flag valid code as errors.
These are false positives — the application runs correctly.

**Fix:** Either suppress the "Type checker" inspection in IDE settings,
or run the application directly to confirm it works despite the warnings.
The warnings do not represent actual bugs.

---

*HUNTER Project Documentation — generated April 2026*

