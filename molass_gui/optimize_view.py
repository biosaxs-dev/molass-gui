"""OptimizeView — Step B: trigger rigorous optimization, poll live_status()."""
import threading
import tkinter as tk
from tkinter import ttk


class OptimizeView:
    """Status window: launches optimize_rigorously() and polls run_info every second."""

    def __init__(self, score, estimator, analysis_folder, parent=None):
        self._score = score
        self._est = estimator
        self._analysis_folder = analysis_folder
        self._parent = parent
        self._run_info = None

    def show(self):
        win = tk.Toplevel(self._parent)
        win.title("Rigorous Optimization")
        win.resizable(False, False)

        f = ttk.Frame(win, padding=12)
        f.pack(fill=tk.BOTH, expand=True)

        ttk.Label(f, text="Status:").grid(row=0, column=0, sticky=tk.W)
        self._status_var = tk.StringVar(value="Starting\u2026")
        ttk.Label(f, textvariable=self._status_var, width=36).grid(
            row=0, column=1, sticky=tk.W, padx=6)

        ttk.Label(f, text="Best SV:").grid(row=1, column=0, sticky=tk.W, pady=6)
        self._sv_var = tk.StringVar(value="\u2014")
        ttk.Label(f, textvariable=self._sv_var, font=("", 14, "bold")).grid(
            row=1, column=1, sticky=tk.W, padx=6)

        ttk.Label(f, text="Evaluations:").grid(row=2, column=0, sticky=tk.W)
        self._n_var = tk.StringVar(value="0")
        ttk.Label(f, textvariable=self._n_var).grid(row=2, column=1, sticky=tk.W, padx=6)

        self._stop_btn = ttk.Button(f, text="Terminate", command=self._stop, state="disabled")
        self._stop_btn.grid(row=3, column=0, columnspan=2, pady=10)

        self._win = win
        threading.Thread(target=self._launch, daemon=True).start()

    def _launch(self):
        try:
            decomp = self._est.decomposition
            run_info = decomp.optimize_rigorously(
                trimmed_ssd=self._est.trimmed_ssd,
                in_process=True,
                async_=True,
                monitor=False,
                analysis_folder=self._analysis_folder,
            )
            self._run_info = run_info
            self._win.after(0, self._on_started)
        except Exception as exc:
            msg = str(exc)
            self._win.after(0, lambda: self._status_var.set(f"Error: {msg}"))

    def _on_started(self):
        self._stop_btn.state(["!disabled"])
        self._status_var.set("Running\u2026")
        self._win.after(1000, self._poll)

    def _poll(self):
        if self._run_info is None:
            return
        try:
            status = self._run_info.live_status()
            phase = status.get('phase', '?')
            best_sv = status.get('best_sv')
            n_evals = status.get('n_evals', 0)
            self._n_var.set(str(n_evals))
            if best_sv is not None:
                self._sv_var.set(f"{best_sv:.2f}")
            if phase == 'done':
                self._status_var.set("Done.")
                self._stop_btn.state(["disabled"])
                return
            self._status_var.set(f"Phase: {phase}")
        except Exception as exc:
            self._status_var.set(f"Poll error: {exc}")
        self._win.after(1000, self._poll)

    def _stop(self):
        if self._run_info is not None:
            try:
                self._run_info.stop()
            except Exception:
                pass
        self._status_var.set("Terminating\u2026")
        self._stop_btn.state(["disabled"])
