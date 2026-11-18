"""ViewAnalysisView — Open Existing Analysis: analysis-folder input (child of Launcher).

Mirrors app.py's data-folder picker, but for an existing optimizer output
folder (must contain optimized/recipe.json). Leads into RigorousView's
static/result mode instead of NaiveView.
"""
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from molass_gui import busy, recent_folders


class ViewAnalysisView:
    def __init__(self, parent=None, app_root=None):
        self._parent = parent
        self._app_root = app_root

    def show(self):
        win = tk.Toplevel(self._parent)
        win.title("Molass — Open Existing Analysis")
        win.resizable(False, False)
        win.protocol("WM_DELETE_WINDOW", self._app_root.close_session)
        self._win = win
        self._build_ui()

    def _build_ui(self):
        f = ttk.Frame(self._win, padding=16)
        f.pack(fill=tk.BOTH, expand=True)

        recent = recent_folders.load(kind="analysis")
        width = recent_folders.picker_width(recent)
        ttk.Label(f, text="Analysis folder:").grid(row=0, column=0, sticky=tk.W, pady=4)
        self._folder_var = tk.StringVar(value="")
        ttk.Entry(f, textvariable=self._folder_var, width=width).grid(
            row=0, column=1, padx=6)
        ttk.Button(f, text="Browse…", command=self._browse).grid(row=0, column=2)

        if recent:
            ttk.Label(f, text="Recent:").grid(row=1, column=0, sticky=tk.W, pady=4)
            self._recent_var = tk.StringVar(value="(custom folder)")
            ttk.Combobox(f, textvariable=self._recent_var,
                        values=["(custom folder)"] + recent,
                        state="readonly", width=width).grid(
                row=1, column=1, columnspan=2, sticky=tk.W, padx=6)
            self._recent_var.trace_add('write', self._on_recent_change)

        self._btn = ttk.Button(f, text="View", command=self._run, style="Accent.TButton")
        self._btn.grid(row=2, column=0, columnspan=3, pady=10)

        self._status_var = tk.StringVar(value="Ready.")
        ttk.Label(f, textvariable=self._status_var, foreground="gray").grid(
            row=3, column=0, columnspan=3, sticky=tk.W)

    def _on_recent_change(self, *_):
        path = self._recent_var.get()
        if path and path != "(custom folder)":
            self._folder_var.set(path)

    def _browse(self):
        d = filedialog.askdirectory(title="Select analysis folder")
        if d:
            self._folder_var.set(d)

    def _run(self):
        folder = self._folder_var.get().strip()
        if not folder:
            messagebox.showwarning("No Folder Selected",
                                    "Please select an analysis folder before clicking View.")
            return

        recipe_path = os.path.join(folder, "optimized", "recipe.json")
        if not os.path.isfile(recipe_path):
            # Common mistake: selected the "optimized" subfolder itself rather than
            # its parent (the actual analysis_folder) -- recipe.json sits directly
            # inside it in that case, so this is unambiguous to auto-correct.
            if os.path.isfile(os.path.join(folder, "recipe.json")):
                folder = os.path.dirname(folder.rstrip("\\/"))
                self._folder_var.set(folder)
            else:
                messagebox.showerror(
                    "Not an Analysis Folder",
                    f"No optimized/recipe.json found in:\n{folder}\n\n"
                    "Select the output folder passed as analysis_folder= to a "
                    "prior rigorous optimization run.")
                return

        # The load runs on the main thread for as long as it takes (minutes on large data), so nothing repaints
        # meanwhile. This window therefore stays up with the hourglass and says which step is going on, and the
        # result window stays hidden until it is drawn; only then does this window give way. A failure comes back
        # here (the hidden window is closed), so that another folder can be tried.
        token = busy.begin(self._win, self._status_var, "Loading the analysis\u2026", buttons=[self._btn],
                           key="open-existing", blocking=True)
        if token is None:
            return
        recent_folders.add(folder, kind="analysis")
        session_tag = os.path.basename(folder.rstrip("\\/")) or folder
        from molass_gui.rigorous_view import RigorousView
        from molass_gui.window_tree import close_window
        holder = {}

        def on_progress(message):
            token.update(message, blocking=True)

        def on_done(error):
            view = holder["view"]
            if error is None:
                token.end(status="")
                view._win.deiconify()
                view._win.lift()
                self._win.withdraw()  # unmap, not just minimize -- keeps only RigorousView on the taskbar
            else:
                token.end(status=f"Could not load: {error}")
                close_window(view._win)

        holder["view"] = RigorousView.open_existing(folder, parent=self._win, app_root=self._app_root,
                                                    session_tag=session_tag, on_progress=on_progress,
                                                    on_done=on_done)
        try:
            holder["view"].show()
        except Exception as exc:
            token.end(status=f"Could not load: {exc}"[:200])
            raise
