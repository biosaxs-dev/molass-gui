"""Plot Components dialog -- on-demand view of the current/best result's
decomposition plot, mirroring params_dialog.py's lazy-build pattern.

Always reloads the latest completed job from disk rather than caching --
the whole point is to see the CURRENT best, which may have improved since
the dialog was last opened (e.g. after Resume produces new jobs).
"""
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


def _export_data(result, parent_win):
    """Write each XR component's jcurve array to '<folder>/component_{i+1}.dat'.

    Same format/convention as the tutorial's "How to Export" section
    (quick_start.ipynb) -- plain np.savetxt of the (qv, I, error) columns --
    so users following the tutorial recognize the GUI's output immediately.
    """
    import numpy as np

    folder = filedialog.askdirectory(title="Select export folder", parent=parent_win)
    if not folder:
        return

    try:
        components = result.get_xr_components()
        for i, comp in enumerate(components):
            path = os.path.join(folder, f"component_{i + 1}.dat")
            np.savetxt(path, comp.get_jcurve_array())
    except Exception as exc:
        messagebox.showerror("Export failed", str(exc), parent=parent_win)
        return

    messagebox.showinfo(
        "Export complete",
        f"Exported {len(components)} component curve(s) to:\n{folder}",
        parent=parent_win,
    )


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
        jobid = min(jobs, key=lambda j: j.best_fv).id if jobs else None
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
              command=lambda: _export_data(result, dlg)).pack(side=tk.LEFT, padx=4)
    ttk.Button(btn_row, text="Close", command=dlg.destroy).pack(side=tk.LEFT, padx=4)
