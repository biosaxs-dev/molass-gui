"""Kratky Shape Match dialog -- on-demand view of the current/best result's
Kratky-plot shape-match diagnostic, mirroring plot_components_dialog.py's
lazy-build pattern.

Always reloads the latest completed job from disk rather than caching --
same rationale as Plot Components: the current best may have improved
since the dialog was last opened (e.g. after Resume produces new jobs).
"""
import tkinter as tk
from tkinter import ttk

from molass_gui.best_result import load_best_result


def show_kratky_shape_match_lazy(win, status_var, decomp, analysis_folder, rgcurve=None, xr_ranks=None):
    """Load the best completed result from *analysis_folder* and show its
    plot_kratky_shape_match() figure in a Toplevel dialog.

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
        Per-component rank override, same as show_plot_components_lazy().
    """
    prev = status_var.get()
    status_var.set("Loading current result\u2026")
    win.update_idletasks()
    try:
        # the true global best, not just the latest job (see best_result.py)
        result = load_best_result(win, decomp, analysis_folder, rgcurve=rgcurve, xr_ranks=xr_ranks)
        if result is None:
            return
    finally:
        status_var.set(prev)

    show_kratky_shape_match_for_result(win, result)


def show_kratky_shape_match_for_result(win, result):
    """Show the Kratky Shape Match dialog for an already-loaded *result*.

    Lets other dialogs (e.g. Plot Components) show the diagnostic for exactly
    the result they display, without reloading from disk. *win* should be a
    long-lived window (the main view, not the calling dialog), so closing the
    caller doesn't destroy this dialog's Toplevel without releasing its figure.
    """
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

    dlg = tk.Toplevel(win)
    dlg.title("Kratky Shape Match")

    # One overlay window, redrawn in place by each double-click on the heatmap.
    overlay = {}

    def _show_overlay(res, component, shape):
        from matplotlib.figure import Figure
        from molass.Kratky.ShapeMatch import plot_kratky_overlay
        from molass_gui.plot_embed import embed_plot, close_dialog_figure

        odlg = overlay.get("dlg")
        if odlg is not None and odlg.winfo_exists():
            plot_kratky_overlay(res, component, shape, fig=overlay["fig"])
            overlay["canvas"].draw()
            odlg.lift()
            return
        odlg = tk.Toplevel(dlg)
        odlg.title("Kratky plot overlay")
        ofig = Figure(figsize=(7, 6))
        plot_kratky_overlay(res, component, shape, fig=ofig)
        canvas, _, _ = embed_plot(odlg, ofig)
        _oclose = lambda: close_dialog_figure(odlg, ofig)
        ttk.Button(odlg, text="Close", command=_oclose).pack(pady=8)
        odlg.protocol("WM_DELETE_WINDOW", _oclose)
        overlay.update(dlg=odlg, fig=ofig, canvas=canvas)

    plot_result = result.plot_kratky_shape_match(on_dblclick=_show_overlay)

    canvas = FigureCanvasTkAgg(plot_result.fig, master=dlg)
    canvas.draw()
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    NavigationToolbar2Tk(canvas, dlg).update()

    btn_row = ttk.Frame(dlg)
    btn_row.pack(pady=8)
    from molass_gui.plot_embed import close_dialog_figure
    _close = lambda: close_dialog_figure(dlg, plot_result.fig)

    series = {}

    def _show_series():
        from matplotlib.figure import Figure
        from molass_gui.plot_embed import embed_plot, close_dialog_figure as _cdf

        sdlg = series.get("dlg")
        if sdlg is not None and sdlg.winfo_exists():
            sdlg.lift()
            return
        sdlg = tk.Toplevel(dlg)
        sdlg.title("Kratky plots of all components")
        sfig = Figure(figsize=(12, 5.2))
        result.plot_kratky_series(fig=sfig)
        embed_plot(sdlg, sfig)
        _sclose = lambda: _cdf(sdlg, sfig)
        ttk.Button(sdlg, text="Close", command=_sclose).pack(pady=8)
        sdlg.protocol("WM_DELETE_WINDOW", _sclose)
        series["dlg"] = sdlg

    ttk.Button(btn_row, text="Compare components", command=_show_series).pack(side=tk.LEFT, padx=4)
    ttk.Button(btn_row, text="Close", command=_close).pack(side=tk.LEFT, padx=4)
    dlg.protocol("WM_DELETE_WINDOW", _close)
