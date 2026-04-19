"""
hunter/controllers/export_controller.py
=========================================
Handles all three export formats: JSON, Word (.docx via Node.js), and
plain-text questionnaire.

Word export pipeline
--------------------
Word export is implemented in JavaScript (export_docx.js) using the
``docx`` npm package, because Python's docx libraries do not support
the professional formatting required.  This controller:

1. Locates the ``node`` executable on the user's system.
2. Checks whether the ``docx`` npm package is installed locally (in the
   project's ``node_modules/`` folder).  If not, offers to install it
   automatically using a background thread so the UI stays responsive.
3. Serialises the plan to a temporary JSON file.
4. Spawns ``node export_docx.js <tmp.json> <output.docx>``.
5. Cleans up the temporary file regardless of success or failure.

npm on Windows
--------------
``npm`` is a ``.cmd`` batch file on Windows — it cannot be invoked
directly via ``subprocess.run(["npm", ...])`` without ``shell=True``.
``_find_npm`` tries four strategies in priority order to locate a
working npm invocation.
"""

import json
import os
import shutil
import subprocess
import threading
from datetime import datetime
from tkinter import messagebox, filedialog
import tkinter as tk

from hunter.theme import THEME


class ExportController:
    """Stateless export helpers.

    All methods are either ``@staticmethod`` or ``@classmethod`` because
    this controller holds no state of its own — it operates entirely on
    the plan data passed to it at call time.
    """

    # ── JSON export ───────────────────────────────────────────────────────────

    @staticmethod
    def export_json(plan_dict: dict) -> None:
        """Prompt for a save path and write the plan as formatted JSON."""
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            initialfile=f"hunt_plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        )
        if not path:
            return   # user cancelled the dialog

        with open(path, "w", encoding="utf-8") as f:
            json.dump(plan_dict, f, indent=2)
        messagebox.showinfo("Export Complete", f"Hunt plan exported to:\n{path}")

    # ── Questionnaire export ──────────────────────────────────────────────────

    @staticmethod
    def export_questionnaire(plan_modules: list[dict]) -> None:
        """Write all questionnaire items from the plan to a plain-text file.

        Each question gets a numbered Q## label, an answer line, and a
        notes/evidence line.  Questions are grouped under their module name.
        """
        # Flatten all questions with their module name
        all_q = [
            (m["name"], q)
            for m in plan_modules
            for q in m.get("questions", [])
        ]
        if not all_q:
            messagebox.showwarning(
                "No Questions",
                "None of the plan modules have questionnaire items."
            )
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt")],
            initialfile=f"HUNTER_Questionnaire_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
        )
        if not path:
            return

        # Build the text content
        lines = [
            "=" * 70,
            "  HUNTER — THREAT HUNT PRE-ENGAGEMENT QUESTIONNAIRE",
            f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"  Modules in Plan : {len(plan_modules)}",
            f"  Total Questions : {len(all_q)}",
            "=" * 70, "",
            "  INSTRUCTIONS:",
            "  Complete this questionnaire with the mission partner prior to",
            "  or at the outset of the threat hunt engagement.  Accurate and",
            "  complete responses ensure hunt actions are performed safely,",
            "  within authorized scope, and with appropriate tooling available.",
            "", "=" * 70, "",
        ]

        q_num = 1
        cur_mod = None
        for mod_name, question in all_q:
            # Print module header when the module changes
            if mod_name != cur_mod:
                cur_mod = mod_name
                lines += ["", f"  ── {mod_name.upper()} ──",
                          "  " + "─" * 62, ""]
            lines += [
                f"  Q{q_num:02d}. {question}", "",
                "        Answer:",
                "        " + "_" * 58, "",
                "        Notes / Evidence:",
                "        " + "_" * 58,
                "        " + "_" * 58, "",
                "  " + "·" * 66, "",
            ]
            q_num += 1

        lines += [
            "", "=" * 70,
            "  END OF QUESTIONNAIRE  —  HUNTER Threat Hunt Plan Builder",
            "=" * 70,
        ]

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        messagebox.showinfo(
            "Export Complete",
            f"Questionnaire ({len(all_q)} questions) exported to:\n{path}"
        )

    # ── Node / npm discovery ──────────────────────────────────────────────────

    @staticmethod
    def find_node() -> str | None:
        """Locate the ``node`` executable and return its absolute path.

        Search order:
        1. ``shutil.which("node")``  — covers PATH on all platforms.
        2. ``shutil.which("node.exe")``  — explicit Windows extension.
        3. Common hard-coded Windows install locations (Program Files,
           nvm-windows, LOCALAPPDATA/Programs/nodejs).

        Returns None if Node.js is not found.
        """
        # Standard PATH lookup (works on Linux, macOS, and most Windows installs)
        found = shutil.which("node") or shutil.which("node.exe")
        if found:
            return found

        # Fallback: common Windows paths that are sometimes not on PATH
        for pf in [
            os.environ.get("PROGRAMFILES", ""),
            os.environ.get("PROGRAMFILES(X86)", ""),
            os.path.join(os.environ.get("APPDATA", ""), "nvm"),        # nvm-windows
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "nodejs"),
        ]:
            if pf:
                candidate = os.path.join(pf, "nodejs", "node.exe")
                if os.path.exists(candidate):
                    return candidate

        return None   # Node.js not found

    @staticmethod
    def find_npm(node_cmd: str) -> dict:
        """Return a dict with keys ``cmd`` and ``shell`` for running npm install.

        On Windows, ``npm`` is ``npm.cmd`` — a batch file that cannot be
        launched with ``shell=False``.  We try four strategies:

        1. Look for ``npm.cmd`` or ``npm`` next to the node executable.
        2. Look for ``npm-cli.js`` (the underlying JS script) and run it
           directly through node — bypasses the .cmd wrapper entirely.
        3. Use ``shutil.which`` to find npm on PATH.
        4. Fall back to ``shell=True`` which lets cmd.exe resolve .cmd files.
        """
        node_dir = os.path.dirname(os.path.abspath(node_cmd))

        # Strategy 1: npm.cmd / npm next to node.exe
        for name in ("npm.cmd", "npm"):
            c = os.path.join(node_dir, name)
            if os.path.exists(c):
                return {"cmd": [c, "install", "docx"], "shell": False}

        # Strategy 2: npm-cli.js (run directly through node)
        npm_cli = os.path.join(
            node_dir, "node_modules", "npm", "bin", "npm-cli.js"
        )
        if os.path.exists(npm_cli):
            return {"cmd": [node_cmd, npm_cli, "install", "docx"], "shell": False}

        # Strategy 3: shutil.which
        for name in ("npm.cmd", "npm"):
            found = shutil.which(name)
            if found:
                return {"cmd": [found, "install", "docx"], "shell": False}

        # Strategy 4: shell=True (last resort — cmd.exe resolves .cmd)
        return {"cmd": "npm install docx", "shell": True}

    # ── npm package installation ──────────────────────────────────────────────

    @classmethod
    def run_npm_install(
        cls,
        parent_window: tk.Misc,
        script_dir: str,
        node_cmd: str,
    ) -> bool:
        """Install the ``docx`` npm package in *script_dir* on a background thread.

        Shows a modal progress window with an animated bar so the Tk event
        loop keeps running while npm downloads the package (which can take
        up to 30 seconds on slow connections).

        Returns True on success, False on failure.
        """
        npm_spec = cls.find_npm(node_cmd)

        # ── Progress dialog ───────────────────────────────────────────────────
        pw = tk.Toplevel(parent_window)
        pw.title("Installing docx package...")
        pw.configure(bg=THEME["bg_dark"])
        pw.geometry("500x180")
        pw.resizable(False, False)
        pw.grab_set()   # make modal — blocks interaction with the main window

        tk.Label(
            pw, text="Installing npm package: docx",
            font=("Courier", 11, "bold"), fg=THEME["accent"],
            bg=THEME["bg_dark"],
        ).pack(pady=(28, 4))
        tk.Label(
            pw, text="Downloading from npm registry — may take ~30 s",
            font=("Courier", 9), fg=THEME["text_secondary"],
            bg=THEME["bg_dark"],
        ).pack()

        # Animated progress bar (a moving segment inside a fixed frame)
        bar_frame = tk.Frame(pw, bg=THEME["border"], height=6)
        bar_frame.pack(fill=tk.X, padx=30, pady=18)
        bar = tk.Frame(bar_frame, bg=THEME["accent"], height=6)
        bar.place(x=0, y=0, height=6, width=0)
        pw.update()

        result: dict = {}   # shared between main thread and worker thread

        def _animate(step: int = 0) -> None:
            """Move the bar segment left-to-right while install is running."""
            if "done" not in result:
                total_w = max(bar_frame.winfo_width(), 1)
                seg = min(140, total_w // 2)
                pos = (step * 6) % (total_w + seg)
                x = pos - seg
                bar.place(
                    x=max(x, 0), y=0,
                    width=min(seg, total_w - max(x, 0)), height=6,
                )
                pw.after(40, lambda: _animate(step + 1))

        def _worker() -> None:
            """Run npm install in a background thread; populate *result* when done."""
            try:
                r = subprocess.run(
                    npm_spec["cmd"],
                    capture_output=True, text=True,
                    cwd=script_dir, shell=npm_spec["shell"],
                    timeout=240,
                )
                result["returncode"] = r.returncode
                result["stderr"]     = r.stderr
                result["stdout"]     = r.stdout
            except subprocess.TimeoutExpired:
                result["returncode"] = -1
                result["stderr"]     = "npm install timed out after 240 seconds."
            except Exception as exc:
                result["returncode"] = -1
                result["stderr"]     = str(exc)
            finally:
                result["done"] = True   # signal _poll that we are finished

        threading.Thread(target=_worker, daemon=True).start()
        _animate()   # start animation on main thread (safe — it uses pw.after)

        success = [False]   # mutable container so _poll can write to it

        def _poll() -> None:
            """Called every 80 ms; closes the dialog when the worker finishes."""
            if "done" not in result:
                pw.after(80, _poll)
                return
            pw.destroy()
            if result.get("returncode", -1) == 0:
                success[0] = True
                messagebox.showinfo(
                    "Package Installed",
                    "docx installed successfully.  Proceeding with export."
                )
            else:
                err = result.get("stderr", "") or result.get("stdout", "")
                messagebox.showerror(
                    "npm Install Failed",
                    "Could not install the docx package automatically.\n\n"
                    f"Open a terminal in:\n  {script_dir}\n\n"
                    f"and run:  npm install docx\n\nError:\n{err[:500]}"
                )

        pw.after(80, _poll)
        pw.wait_window()   # block the calling code until the dialog closes
        return success[0]

    # ── Word export ───────────────────────────────────────────────────────────

    @staticmethod
    def export_word(
        parent_window: tk.Misc,
        plan_dict: dict,
        script_dir: str,
    ) -> None:
        """Run the full Word export pipeline.

        Steps:
        1. Verify export_docx.js is present in *script_dir*.
        2. Find node.js on the system.
        3. Ensure the docx npm package is installed locally; offer to install
           it if missing.
        4. Ask the user for an output .docx file path.
        5. Write the plan to a temporary JSON file.
        6. Run: node export_docx.js <tmp.json> <output.docx>
        7. Clean up the temporary JSON file.

        *script_dir* must be the project root (the directory that contains
        both ``main.py`` and ``export_docx.js``).
        """
        # ── Step 1: verify the JS export script exists ────────────────────────
        docx_script = os.path.join(script_dir, "export_docx.js")
        if not os.path.exists(docx_script):
            messagebox.showerror(
                "Missing File",
                f"export_docx.js not found in:\n{script_dir}\n\n"
                "Make sure export_docx.js is in the same folder as main.py."
            )
            return

        # ── Step 2: find node ─────────────────────────────────────────────────
        node_cmd = ExportController.find_node()
        if node_cmd is None:
            messagebox.showerror(
                "Node.js Not Found",
                "Node.js is required for Word export.\n"
                "Download and install from https://nodejs.org, "
                "then restart HUNTER."
            )
            return

        # ── Step 3: ensure docx npm package is installed ─────────────────────
        node_modules = os.path.join(script_dir, "node_modules", "docx")
        if not os.path.isdir(node_modules):
            if not messagebox.askyesno(
                "Install Required Package",
                "The 'docx' npm package is not installed yet.\n\n"
                f"HUNTER will run:  npm install docx\nin:  {script_dir}\n\n"
                "This is a one-time setup (~5 MB download).  Proceed?"
            ):
                return
            ok = ExportController.run_npm_install(parent_window, script_dir, node_cmd)
            # Re-check: if install failed the folder still won't exist
            if not ok or not os.path.isdir(node_modules):
                return

        # ── Step 4: ask for output path ───────────────────────────────────────
        path = filedialog.asksaveasfilename(
            defaultextension=".docx",
            filetypes=[("Word Documents", "*.docx")],
            initialfile=(
                f"HUNTER_Hunt_Plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
            ),
        )
        if not path:
            return   # user cancelled the dialog

        # ── Steps 5–7: write JSON, run node, clean up ─────────────────────────
        tmp_json = os.path.join(script_dir, "_tmp_hunt_plan.json")
        with open(tmp_json, "w", encoding="utf-8") as f:
            json.dump(plan_dict, f, indent=2)

        try:
            r = subprocess.run(
                [node_cmd, docx_script, tmp_json, path],
                capture_output=True, text=True,
                cwd=script_dir,      # ensures local node_modules is found
                timeout=60,
            )
            if r.returncode == 0:
                messagebox.showinfo(
                    "Export Complete", f"Word document exported to:\n{path}"
                )
            else:
                # Show the first 1200 chars of node's stderr for diagnosis
                messagebox.showerror(
                    "Export Failed",
                    f"export_docx.js returned an error:\n\n{r.stderr[:1200]}"
                )
        except subprocess.TimeoutExpired:
            messagebox.showerror(
                "Export Timeout",
                "The Node.js export script timed out after 60 seconds."
            )
        except Exception as exc:
            messagebox.showerror("Export Error", str(exc))
        finally:
            # Always remove the temp file, even if export failed
            try:
                os.remove(tmp_json)
            except Exception:
                pass
