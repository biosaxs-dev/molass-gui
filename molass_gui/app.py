"""molass-gui — Phase 1: data folder input."""
import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog

_DEFAULT_FOLDER = r"C:\Users\takahashi\PyTools\Data\20230705"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Molass")
        self.resizable(False, False)
        self._configure_style()
        self._cleanup_callbacks = []
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.close_session)

    def register_cleanup(self, fn):
        """Called by RigorousView so an active optimizer subprocess is stopped
        when the session (this window + every child phase window) is closed."""
        self._cleanup_callbacks.append(fn)

    def close_session(self):
        """Close every window that belongs to this session in one action --
        wired to the close button of the root AND every child phase window,
        so closing any one of them tears down the whole session, not just itself."""
        for fn in self._cleanup_callbacks:
            try:
                fn()
            except Exception:
                pass
        self.destroy()
        import sys
        sys.exit(0)

    def _configure_style(self):
        # 'clam' honors custom background/foreground on TButton, unlike the
        # native 'vista' theme -- needed for Accent/Danger to actually show.
        style = ttk.Style(self)
        style.theme_use('clam')

        style.configure('Accent.TButton', background='#2563eb', foreground='white',
                         padding=6)
        style.map('Accent.TButton',
                  background=[('active', '#1d4ed8'), ('disabled', '#93b4f5')])

        style.configure('Danger.TButton', background='#dc2626', foreground='white',
                         padding=6)
        style.map('Danger.TButton',
                  background=[('active', '#b91c1c'), ('disabled', '#eba6a6')])

    def _build_ui(self):
        f = ttk.Frame(self, padding=16)
        f.pack(fill=tk.BOTH, expand=True)

        ttk.Label(f, text="Data folder:").grid(row=0, column=0, sticky=tk.W, pady=4)
        self._folder_var = tk.StringVar(value=_DEFAULT_FOLDER)
        ttk.Entry(f, textvariable=self._folder_var, width=52).grid(
            row=0, column=1, padx=6)
        ttk.Button(f, text="Browse…", command=self._browse).grid(row=0, column=2)

        self._btn = ttk.Button(f, text="Load", command=self._run)
        self._btn.grid(row=1, column=0, columnspan=3, pady=10)

        self._status_var = tk.StringVar(value="Ready.")
        ttk.Label(f, textvariable=self._status_var, foreground="gray").grid(
            row=2, column=0, columnspan=3, sticky=tk.W)

    def _browse(self):
        d = filedialog.askdirectory(title="Select data folder")
        if d:
            self._folder_var.set(d)

    def _run(self):
        folder = self._folder_var.get().strip()
        if not folder:
            self._status_var.set("Please select a data folder first.")
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
                    session_tag = os.path.basename(folder.rstrip("\\/")) or folder
                    from molass_gui.naive_view import NaiveView
                    NaiveView(ssd, trimmed, parent=self, app_root=self,
                              session_tag=session_tag).show()

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
