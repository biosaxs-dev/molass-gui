"""Shape Analysis dialog -- on-demand view of the current/best result's
Kratky-plot shape-match diagnostic, mirroring plot_components_dialog.py's
lazy-build pattern.

Always reloads the latest completed job from disk rather than caching --
same rationale as Plot Components: the current best may have improved
since the dialog was last opened (e.g. after Resume produces new jobs).
"""
import tkinter as tk
from tkinter import ttk

from molass.Rigorous.CurrentStateUtils import load_rigorous_result, list_rigorous_jobs


def show_shape_analysis_lazy(win, status_var, decomp, analysis_folder, rgcurve=None):
    """Load the best completed result from *analysis_folder* and show its
    plot_shape_analysis() figure in a Toplevel dialog.

    Parameters
    ----------
    win : tk widget
        Parent window for the status update and the dialog.
    status_var : tk.StringVar
        Temporarily shows "Loading current result..." during the (fast) load.
    decomp : Decomposition
        The initial (pre-rigorous) decomposition -- provides ssd/model type.
    analysis_folder : str
    rgcurve : RgCurve, optional
        Pre-computed Rg curve to avoid redundant Guinier fitting.
    """
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

    prev = status_var.get()
    status_var.set("Loading current result\u2026")
    win.update_idletasks()
    try:
        # same "true global-best, not just latest" job selection as
        # plot_components_dialog.py -- keeps this dialog's SV-implied result
        # consistent with the header panels.
        jobs = list_rigorous_jobs(analysis_folder)
        if not jobs:
            from tkinter import messagebox
            messagebox.showinfo(
                "No results yet",
                "The optimization hasn't produced its first result yet.\n"
                "Try again in a moment.",
                parent=win,
            )
            return
        jobid = min(jobs, key=lambda j: j.best_fv).id
        result = load_rigorous_result(decomp, analysis_folder, jobid=jobid, rgcurve=rgcurve)
    finally:
        status_var.set(prev)

    plot_result = result.plot_shape_analysis()

    dlg = tk.Toplevel(win)
    dlg.title("Shape Analysis")
    canvas = FigureCanvasTkAgg(plot_result.fig, master=dlg)
    canvas.draw()
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    NavigationToolbar2Tk(canvas, dlg).update()

    btn_row = ttk.Frame(dlg)
    btn_row.pack(pady=8)
    ttk.Button(btn_row, text="Close", command=dlg.destroy).pack(side=tk.LEFT, padx=4)
