"""Plot Components dialog -- on-demand view of the current/best result's
decomposition plot, mirroring params_dialog.py's lazy-build pattern.

Always reloads the latest completed job from disk rather than caching --
the whole point is to see the CURRENT best, which may have improved since
the dialog was last opened (e.g. after Resume produces new jobs).
"""
import tkinter as tk
from tkinter import messagebox, ttk

from molass_gui.plot_embed import export_component_data


def show_plot_components_lazy(win, status_var, decomp, analysis_folder, rgcurve=None):
    """Load the best completed result from *analysis_folder* and show its
    plot_components() figure in a Toplevel dialog.

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
    from molass.Rigorous.CurrentStateUtils import load_rigorous_result, list_rigorous_jobs

    prev = status_var.get()
    status_var.set("Loading current result\u2026")
    win.update_idletasks()
    try:
        # load_rigorous_result(jobid=None) defaults to the LATEST job, not the
        # best one -- pass the true global-best id explicitly so this always
        # matches the SV already shown in the header panels (confirmed to
        # diverge in practice: a later job can be marginally worse than an
        # earlier one, e.g. a reseeded round that hasn't yet improved on it).
        jobs = list_rigorous_jobs(analysis_folder)
        if not jobs:
            # e.g. clicked right after launch -- callback.txt only has the
            # init-params entry, no search step has completed yet (issue #188
            # guard in list_rigorous_jobs excludes it) -- not an error.
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

    plot_result = result.plot_components(rgcurve=rgcurve, rg_cmap='YlGn',
                                         rg_alpha_by_score=True, rg_alpha_power=2.5)

    dlg = tk.Toplevel(win)
    dlg.title("Plot Components")
    canvas = FigureCanvasTkAgg(plot_result.fig, master=dlg)
    canvas.draw()
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    NavigationToolbar2Tk(canvas, dlg).update()

    btn_row = ttk.Frame(dlg)
    btn_row.pack(pady=8)
    ttk.Button(btn_row, text="Export Data\u2026",
              command=lambda: export_component_data(result, dlg)).pack(side=tk.LEFT, padx=4)
    ttk.Button(btn_row, text="Close", command=dlg.destroy).pack(side=tk.LEFT, padx=4)
