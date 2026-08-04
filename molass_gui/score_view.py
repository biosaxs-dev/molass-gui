"""ScoreView — shows score plot with an Optimize button."""
import tkinter as tk
from tkinter import ttk, filedialog
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk


class ScoreView:
    """Score plot window; Optimize button triggers folder picker → OptimizeView."""

    def __init__(self, score, estimator, parent=None):
        self._score = score
        self._est = estimator
        self._parent = parent

    def show(self):
        title = f"Initial score \u2014 SV={self._score.sv:.2f}"
        win = tk.Toplevel(self._parent) if self._parent is not None else tk.Tk()
        win.title(title)

        plot_result = self._score.plot(title=title)
        ax_uv, ax_xr, ax_score = plot_result.axes[:3]
        ax_uv.set_title("UV Decomposition", fontsize=16)
        ax_xr.set_title("XR Decomposition", fontsize=16)
        ax_score.set_title(f"Score Breakdown  (SV={self._score.sv:.1f})", fontsize=16)
        plot_result.fig.subplots_adjust(top=0.85)
        canvas = FigureCanvasTkAgg(plot_result.fig, master=win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        NavigationToolbar2Tk(canvas, win).update()

        btn_frame = ttk.Frame(win, padding=(4, 4))
        btn_frame.pack(fill=tk.X)
        ttk.Button(btn_frame, text="Optimize\u2026", command=self._run_optimize).pack(
            side=tk.RIGHT, padx=8, pady=4)

        self._win = win

    def _run_optimize(self):
        folder = filedialog.askdirectory(
            title="Select output folder for optimization results",
            parent=self._win,
        )
        if not folder:
            return
        from molass_gui.optimize_view import OptimizeView
        OptimizeView(self._score, self._est, analysis_folder=folder, parent=self._win).show()
