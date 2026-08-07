"""molass-gui — Phase 1: data folder input."""
import threading
import tkinter as tk
from tkinter import ttk, filedialog

_DEFAULT_FOLDER = r"C:\Users\takahashi\PyTools\Data\20230705"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Molass")
        self.resizable(False, False)
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._quit)

    def _quit(self):
        import sys
        self.destroy()
        sys.exit(0)

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
                    from molass_gui.naive_view import NaiveView
                    NaiveView(ssd, trimmed, parent=self).show()

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
