"""molass-gui — Phase 1: data folder input."""
import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from molass_gui import recent_folders


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Molass")
        self.resizable(False, False)
        self._configure_style()
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.close_session)

    def close_session(self):
        """Close every window that belongs to this session in one action --
        wired to the close button of the root AND every child phase window,
        so closing any one of them tears down the whole session, not just itself.
        Confirms first if a long-running job (e.g. rigorous optimization) is
        active anywhere in the session (see window_tree.confirm_and_close)."""
        from molass_gui.window_tree import confirm_and_close
        if confirm_and_close(self):
            import sys
            sys.exit(0)

    def _configure_style(self):
        # 'clam' honors custom background/foreground on TButton, unlike the
        # native 'vista' theme -- needed for Accent/Danger to actually show.
        style = ttk.Style(self)
        style.theme_use('clam')

        style.configure('Accent.TButton', background='#2563eb', foreground='white',
                         padding=6)
        # 'disabled' must precede 'active' -- ttk matches state specs in list
        # order, and the button is still 'active' (mouse still hovering right
        # after the click that disabled it) as well as 'disabled' at that
        # moment, so 'disabled' has to win the match or the background stays
        # looking enabled even though the text correctly turns gray.
        style.map('Accent.TButton',
                  background=[('disabled', '#93b4f5'), ('active', '#1d4ed8')])

        style.configure('Danger.TButton', background='#dc2626', foreground='white',
                         padding=6)
        style.map('Danger.TButton',
                  background=[('disabled', '#eba6a6'), ('active', '#b91c1c')])

    def _build_ui(self):
        f = ttk.Frame(self, padding=16)
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
        ttk.Label(f, textvariable=self._status_var, foreground="gray").grid(
            row=4, column=0, columnspan=3, sticky=tk.W)

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

    def _run(self):
        folder = self._folder_var.get().strip()
        if not folder:
            # A status-label update alone is too easy to miss (small gray text
            # right below the button just clicked) -- a modal prompt guarantees
            # the user notices nothing was loaded.
            messagebox.showwarning("No Folder Selected",
                                    "Please select a data folder before clicking Load.")
            return

        self._btn.state(["disabled"])
        self._status_var.set("Loading…")

        def worker():
            try:
                from molass.DataObjects import SecSaxsData as SSD
                ssd = SSD(folder)
                trimmed = ssd.trimmed_copy()

                def on_main():
                    self._btn.state(["!disabled"])
                    self._status_var.set("Ready.")
                    recent_folders.add(folder)
                    session_tag = os.path.basename(folder.rstrip("\\/")) or folder
                    from molass_gui.session_context import SessionContext
                    ctx = SessionContext(folder)
                    from molass_gui.naive_view import NaiveView
                    NaiveView(ssd, trimmed, ctx, parent=self, app_root=self,
                              session_tag=session_tag).show()
                    self.withdraw()  # unmap, not just minimize -- keeps only NaiveView on the taskbar

                self.after(0, on_main)

            except Exception as exc:
                msg = str(exc)
                def on_error(m=msg):
                    self._status_var.set(f"Error: {m}")
                    self._btn.state(["!disabled"])
                self.after(0, on_error)

        threading.Thread(target=worker, daemon=True).start()


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
