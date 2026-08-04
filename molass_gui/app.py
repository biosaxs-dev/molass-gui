"""
molass-gui — Option A prototype: folder picker → InitialEstimator → score display.

Parallels molass-researcher/experiments/34_ssd_rigorous_gui/34e_standard_way.ipynb:
  SSD(folder) → trimmed_copy → corrected_copy → quick_decomposition
  → decomposition.score(trimmed_ssd) → score.plot()
"""
import threading
import tkinter as tk
from tkinter import ttk, filedialog

_DEFAULT_FOLDER = r"C:\Users\takahashi\PyTools\Data\20230705"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Molass — Initial Estimate")
        self.resizable(False, False)
        self._build_ui()

    def _build_ui(self):
        f = ttk.Frame(self, padding=16)
        f.pack(fill=tk.BOTH, expand=True)

        ttk.Label(f, text="Data folder:").grid(row=0, column=0, sticky=tk.W, pady=4)
        self._folder_var = tk.StringVar(value=_DEFAULT_FOLDER)
        ttk.Entry(f, textvariable=self._folder_var, width=52).grid(
            row=0, column=1, padx=6)
        ttk.Button(f, text="Browse…", command=self._browse).grid(row=0, column=2)

        ttk.Label(f, text="Components:").grid(row=1, column=0, sticky=tk.W, pady=4)
        self._nc_var = tk.IntVar(value=3)
        ttk.Spinbox(f, from_=1, to=6, textvariable=self._nc_var, width=5).grid(
            row=1, column=1, sticky=tk.W, padx=6)

        self._btn = ttk.Button(f, text="Estimate", command=self._run)
        self._btn.grid(row=2, column=0, columnspan=3, pady=10)

        self._status_var = tk.StringVar(value="Ready.")
        ttk.Label(f, textvariable=self._status_var, foreground="gray").grid(
            row=3, column=0, columnspan=3, sticky=tk.W)

    def _browse(self):
        d = filedialog.askdirectory(title="Select data folder")
        if d:
            self._folder_var.set(d)

    def _run(self):
        folder = self._folder_var.get().strip()
        if not folder:
            self._status_var.set("Please select a data folder first.")
            return

        nc = self._nc_var.get()
        self._btn.state(["disabled"])
        self._status_var.set("Loading data…")

        def worker():
            try:
                from molass.DataObjects import SecSaxsData as SSD
                ssd = SSD(folder)
                trimmed = ssd.trimmed_copy()
                corrected = trimmed.corrected_copy()
                decomp = corrected.quick_decomposition(num_components=nc)

                from molass.Rigorous.InitialEstimator import InitialEstimator
                est = InitialEstimator(decomp, trimmed_ssd=trimmed)

                def on_main():
                    self._btn.state(["!disabled"])
                    self._status_var.set("Ready.")
                    est.show(parent=self)

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
