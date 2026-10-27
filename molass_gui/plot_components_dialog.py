"""Plot Components dialog -- on-demand view of the current/best result's
decomposition plot, mirroring params_dialog.py's lazy-build pattern.

Always reloads the latest completed job from disk rather than caching --
the whole point is to see the CURRENT best, which may have improved since
the dialog was last opened (e.g. after Resume produces new jobs).
"""
import tkinter as tk
from tkinter import ttk

from molass_gui.plot_embed import export_component_data
from molass_gui.kratky_shape_match_dialog import show_kratky_shape_match_for_result


def show_plot_components_lazy(win, status_var, decomp, analysis_folder, rgcurve=None, xr_ranks=None):
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
    xr_ranks : list of int, optional
        Per-component rank override (see RigorousView's "Set Ranks…"); falls
        back to ``decomp.xr_ranks`` when None (see ``load_rigorous_result``).
    """
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
    from molass_gui.best_result import load_best_result
    from molass_gui.plot_embed import close_dialog_figure

    prev = status_var.get()
    status_var.set("Loading current result\u2026")
    win.update_idletasks()
    try:
        # the true global best, not just the latest job, so this always matches the SV already shown
        # in the header panels; result.fv / result.sv are attached (lets export() record SV/FV)
        result = load_best_result(win, decomp, analysis_folder, rgcurve=rgcurve, xr_ranks=xr_ranks)
        if result is None:
            return
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
              command=lambda: export_component_data(result, dlg, rgcurve=rgcurve)).pack(side=tk.LEFT, padx=4)
    ttk.Button(btn_row, text="Kratky Shape Match\u2026",
              command=lambda: show_kratky_shape_match_for_result(win, result)).pack(side=tk.LEFT, padx=4)
    _close = lambda: close_dialog_figure(dlg, plot_result.fig)
    ttk.Button(btn_row, text="Close", command=_close).pack(side=tk.LEFT, padx=4)
    dlg.protocol("WM_DELETE_WINDOW", _close)
