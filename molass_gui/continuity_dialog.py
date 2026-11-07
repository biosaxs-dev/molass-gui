"""Continuity dialog -- distinct species or slices of a continuum? (molass-gui#12, molass-library#370)

Shows ``Decomposition.get_continuity_report()``: the verdict with the numbers behind it (text) and
the data Rg curve with the plateaus found and the component Rg values (figure). The verdict is
``discrete``, ``no evidence for distinct species`` or ``undetermined``, never "continuum"; the
dialog adds no interpretation of its own. Computation is cheap once the Rg curve exists, which the
views already hold (it is passed on, not refitted).
"""
import tkinter as tk
from tkinter import ttk

from molass_gui.continuity_logic import UNAVAILABLE_MESSAGE, BUSY_MESSAGE, is_available, window_title, report_text
from molass_gui.plot_embed import embed_plot, close_dialog_figure


def show_continuity(win, status_var, decomp, rgcurve=None, stage=None, heading=None):
    """Compute the continuity report of *decomp* in a background thread and open the dialog.

    The first report of a session takes up to a minute (it builds the Kratky reference-shape
    library, as the first Kratky Shape Match does), later ones 1-3 s; hence the thread.

    ``rgcurve`` is the data Rg curve the view already holds (``decomp.get_rg_curve()`` if None);
    ``stage`` (window title) and ``heading`` (the ``dataset | model | method`` line, e.g.
    ``make_auto_title(decomp)``) tell the figure's stage.
    """
    import threading
    from molass_gui.error_dialog import show_error_detail

    if not is_available(decomp):
        show_error_detail(win, status_var, UNAVAILABLE_MESSAGE, title="Continuity unavailable")
        return
    prev = status_var.get()
    status_var.set(BUSY_MESSAGE)
    box = {}

    def worker():
        try:
            box["report"] = decomp.get_continuity_report(rgcurve=rgcurve)
        except Exception as exc:
            box["err"] = exc

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    def poll():
        if thread.is_alive():
            win.after(300, poll)
            return
        status_var.set(prev)
        if "err" in box:
            show_error_detail(win, status_var, str(box["err"]), title="Continuity report failed")
            return
        ContinuityDialog(win, box["report"], stage=stage, heading=heading)

    win.after(300, poll)


def show_continuity_lazy(win, status_var, decomp, analysis_folder, rgcurve=None, xr_ranks=None):
    """Rigorous stage: load the best completed result from *analysis_folder* (the true global best,
    same job selection as Plot Components) and open the dialog for it."""
    from molass_gui.best_result import load_best_result
    from molass_gui.homogeneity_dialog import _heading

    prev = status_var.get()
    status_var.set("Loading current result\u2026")
    win.update_idletasks()
    try:
        result = load_best_result(win, decomp, analysis_folder, rgcurve=rgcurve, xr_ranks=xr_ranks)
        if result is None:
            return
    finally:
        status_var.set(prev)
    show_continuity(win, status_var, result, rgcurve=rgcurve, stage="Rigorous", heading=_heading(result))


class ContinuityDialog:
    """The report text above, the Rg-curve figure below."""

    def __init__(self, win, report, stage=None, heading=None):
        self.report = report
        dlg = self._dlg = tk.Toplevel(win)
        dlg.title(window_title(stage))
        dlg.geometry("1000x820")

        text = tk.Text(dlg, wrap=tk.WORD, height=17, font=("Courier New", 9))
        text.insert("1.0", report_text(report, heading))
        text.configure(state="disabled")
        text.pack(fill=tk.X, padx=8, pady=(8, 4))

        from matplotlib.figure import Figure
        self._fig = Figure(figsize=(8, 4.5))
        report.plot(fig=self._fig)
        figframe = ttk.Frame(dlg)
        figframe.pack(fill=tk.BOTH, expand=True)
        embed_plot(figframe, self._fig)

        _close = lambda: close_dialog_figure(dlg, self._fig)
        ttk.Button(dlg, text="Close", command=_close).pack(pady=8)
        dlg.protocol("WM_DELETE_WINDOW", _close)
