"""molass-gui — New Analysis: data folder input (child of Launcher)."""
import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from molass_gui import recent_folders
from molass_gui.session_context import to_dropbox_path


class App:
    def __init__(self, parent=None, app_root=None):
        self._parent = parent
        self._app_root = app_root

    def show(self):
        win = tk.Toplevel(self._parent)
        win.title("Molass — New Analysis")
        win.resizable(False, False)
        win.protocol("WM_DELETE_WINDOW", self._app_root.close_session)
        self._win = win
        self._build_ui()

    def _build_ui(self):
        f = ttk.Frame(self._win, padding=16)
        f.pack(fill=tk.BOTH, expand=True)

        ttk.Label(f, text="Data folder:").grid(row=0, column=0, sticky=tk.W, pady=4)
        self._folder_var = tk.StringVar(value="")
        ttk.Entry(f, textvariable=self._folder_var, width=52).grid(
            row=0, column=1, padx=6)
        ttk.Button(f, text="Browse…", command=self._browse).grid(row=0, column=2)

        sample_names = self._discover_samples()
        if sample_names:
            ttk.Label(f, text="Sample:").grid(row=1, column=0, sticky=tk.W, pady=4)
            self._sample_var = tk.StringVar(value="(custom folder)")
            ttk.Combobox(f, textvariable=self._sample_var,
                        values=["(custom folder)"] + sample_names,
                        state="readonly", width=20).grid(
                row=1, column=1, sticky=tk.W, padx=6)
            self._sample_var.trace_add('write', self._on_sample_change)

        recent = recent_folders.load()
        if recent:
            ttk.Label(f, text="Recent:").grid(row=2, column=0, sticky=tk.W, pady=4)
            self._recent_var = tk.StringVar(value="(custom folder)")
            ttk.Combobox(f, textvariable=self._recent_var,
                        values=["(custom folder)"] + recent,
                        state="readonly", width=52).grid(
                row=2, column=1, columnspan=2, sticky=tk.W, padx=6)
            self._recent_var.trace_add('write', self._on_recent_change)

        self._btn = ttk.Button(f, text="Load", command=self._run)
        self._btn.grid(row=3, column=0, columnspan=3, pady=10)

        self._status_var = tk.StringVar(value="Ready.")
        # wraplength caps the label so a long status message (e.g. a full
        # cache path) wraps instead of widening the fixed-size dialog.
        ttk.Label(f, textvariable=self._status_var, foreground="gray", wraplength=400).grid(
            row=4, column=0, columnspan=3, sticky=tk.W)

        # Indeterminate: the Dropbox bulk-zip download has no byte-level
        # progress to report, only a start/end status message.
        self._progress = ttk.Progressbar(f, mode="indeterminate", length=300)

    def _discover_samples(self):
        # molass_data is an optional convenience dependency (test/demo datasets),
        # not a required one -- degrade to no sample selector if it's absent.
        try:
            import molass_data
        except ImportError:
            return []
        return sorted(n for n in dir(molass_data) if n.startswith('SAMPLE'))

    def _on_sample_change(self, *_):
        name = self._sample_var.get()
        if name and name != "(custom folder)":
            import molass_data
            self._folder_var.set(getattr(molass_data, name))

    def _on_recent_change(self, *_):
        path = self._recent_var.get()
        if path and path != "(custom folder)":
            self._folder_var.set(path)

    def _browse(self):
        d = filedialog.askdirectory(title="Select data folder")
        if d:
            self._folder_var.set(d)

    def _connect_dropbox_dialog(self):
        """Blocking one-time OAuth connect flow. Returns True on success."""
        from molass.DataUtils import DropboxSync

        result = {"ok": False}
        win = tk.Toplevel(self._win)
        win.title("Connect to Dropbox")
        win.resizable(False, False)
        win.transient(self._win)
        f = ttk.Frame(win, padding=16)
        f.pack(fill=tk.BOTH, expand=True)

        ttk.Label(f, text="App Key:").grid(row=0, column=0, sticky=tk.W, pady=4)
        app_key_var = tk.StringVar(value="")
        ttk.Entry(f, textvariable=app_key_var, width=40).grid(row=0, column=1, padx=6)

        auth_flow_holder = {}

        def open_browser():
            app_key = app_key_var.get().strip()
            if not app_key:
                messagebox.showwarning("App Key Required", "Please enter an App Key first.", parent=win)
                return
            auth_flow_holder["flow"] = DropboxSync.start_authorize(app_key)
            import webbrowser
            webbrowser.open(auth_flow_holder["flow"].start())

        ttk.Button(f, text="Open Browser…", command=open_browser).grid(row=0, column=2, padx=4)

        ttk.Label(f, text="Code from browser:").grid(row=1, column=0, sticky=tk.W, pady=4)
        code_var = tk.StringVar(value="")
        ttk.Entry(f, textvariable=code_var, width=40).grid(row=1, column=1, padx=6)

        status_var = tk.StringVar(value="")
        ttk.Label(f, textvariable=status_var, foreground="gray").grid(
            row=2, column=0, columnspan=3, sticky=tk.W)

        def connect():
            flow = auth_flow_holder.get("flow")
            if flow is None:
                messagebox.showwarning("Not Started", "Click \"Open Browser…\" first.", parent=win)
                return
            try:
                app_key, refresh_token = DropboxSync.finish_authorize(flow, code_var.get())
                DropboxSync.save_credentials(app_key, refresh_token)
                result["ok"] = True
                win.destroy()
            except Exception as exc:
                status_var.set(f"Error: {exc}")

        ttk.Button(f, text="Connect", command=connect).grid(row=3, column=0, columnspan=3, pady=10)

        win.grab_set()
        win.wait_window()
        return result["ok"]

    def _run(self):
        folder = self._folder_var.get().strip()
        if not folder:
            # A status-label update alone is too easy to miss (small gray text
            # right below the button just clicked) -- a modal prompt guarantees
            # the user notices nothing was loaded.
            messagebox.showwarning("No Folder Selected",
                                    "Please select a data folder before clicking Load.")
            return

        if "dropbox" in folder.lower():
            try:
                from molass.DataUtils import DropboxSync
                DropboxSync.load_credentials()
            except ImportError:
                messagebox.showwarning(
                    "Dropbox Support Not Installed",
                    "This folder looks like a Dropbox path, but Dropbox support isn't "
                    "installed. Install with: pip install molass[dropbox]\n\n"
                    "Proceeding with the local path as-is.")
            except EnvironmentError:
                if not self._connect_dropbox_dialog():
                    return  # user cancelled setup

        self._btn.state(["disabled"])
        self._status_var.set("Loading…")

        def worker():
            actual_folder = folder
            if "dropbox" in folder.lower():
                dropbox_path = to_dropbox_path(folder)
                if dropbox_path:
                    try:
                        from molass.DataUtils import sync_dropbox_folder

                        def on_status(msg, _self=self):
                            _self._win.after(0, lambda: _self._status_var.set(msg))

                        self._win.after(0, lambda: self._progress.grid(
                            row=5, column=0, columnspan=3, sticky=tk.W, pady=(4, 0)))
                        self._win.after(0, lambda: self._progress.start(10))
                        try:
                            actual_folder = sync_dropbox_folder(dropbox_path, on_status=on_status)
                        finally:
                            self._win.after(0, self._progress.stop)
                            self._win.after(0, self._progress.grid_remove)
                    except Exception as exc:
                        # False-positive match or sync failure -- fall back to the
                        # local path directly rather than blocking the load.
                        actual_folder = folder
                        self._win.after(0, lambda e=exc: self._status_var.set(
                            f"Dropbox sync skipped ({e}); using local path"))

            try:
                from molass.DataObjects import SecSaxsData as SSD
                ssd = SSD(actual_folder)
                trimmed = ssd.trimmed_copy()

                def on_main():
                    self._btn.state(["!disabled"])
                    self._status_var.set("Ready.")
                    recent_folders.add(folder)
                    session_tag = os.path.basename(folder.rstrip("\\/")) or folder
                    from molass_gui.session_context import SessionContext
                    ctx = SessionContext(folder)
                    from molass_gui.naive_view import NaiveView
                    NaiveView(ssd, trimmed, ctx, parent=self._win, app_root=self._app_root,
                              session_tag=session_tag).show()
                    self._win.withdraw()  # unmap, not just minimize -- keeps only NaiveView on the taskbar

                self._win.after(0, on_main)

            except Exception as exc:
                msg = str(exc)
                def on_error(m=msg):
                    self._status_var.set(f"Error: {m}")
                    self._btn.state(["!disabled"])
                self._win.after(0, on_error)

        threading.Thread(target=worker, daemon=True).start()
