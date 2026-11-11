"""Mass dialog -- the concentration-free volume-of-correlation mass of the components and along the elution
(molass-gui#13, molass-library#381).

A table of the XR components (Rg, mass in kDa) with the caveat always visible below it, and the per-frame mass
and Rg curves (``VolumeMassCurve.plot()``). The computation reuses the Rg curve the view already holds and runs in
a background thread. The mass is a protein calibration, not an exact value: see ``mass_logic.CAVEAT``.
"""
import tkinter as tk
from tkinter import ttk

from molass_gui.mass_logic import (UNAVAILABLE_MESSAGE, BUSY_MESSAGE, CAVEAT, is_available, window_title,
                                   compute_mass)
from molass_gui import busy
from molass_gui.dpi import geometry, px
from molass_gui.plot_embed import embed_plot, close_dialog_figure


def show_mass(win, status_var, decomp, rgcurve=None, stage=None, heading=None):
    """Compute the masses of *decomp* in a background thread and open the dialog.

    ``rgcurve`` is the data Rg curve the view already holds (``decomp.get_rg_curve()`` if None); ``stage``
    (window title) and ``heading`` (the ``dataset | model | method`` line) tell the stage."""
    import threading
    from molass_gui.error_dialog import show_error_detail

    if not is_available():
        show_error_detail(win, status_var, UNAVAILABLE_MESSAGE, title="Mass unavailable")
        return
    token = busy.begin(win, status_var, BUSY_MESSAGE, key="mass")
    if token is None:
        return      # already being computed
    box = {}

    def worker():
        try:
            box["result"] = compute_mass(decomp, rgcurve=rgcurve)
        except Exception as exc:
            box["err"] = str(exc) or type(exc).__name__

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    def poll():
        if thread.is_alive():
            win.after(300, poll)
            return
        token.end()
        if "err" in box:
            show_error_detail(win, status_var, box["err"], title="Mass failed")
            return
        rows, curve, curve_error = box["result"]
        MassDialog(win, rows, curve, curve_error, stage=stage, heading=heading)

    win.after(300, poll)


def show_mass_lazy(win, status_var, decomp, analysis_folder, rgcurve=None, xr_ranks=None):
    """Rigorous stage: load the best completed result from *analysis_folder* (the true global best, the same job
    selection as Plot Components) and open the dialog for it."""
    from molass_gui.best_result import load_best_result
    from molass_gui.homogeneity_dialog import _heading

    with busy.working(win, status_var, "Loading current result\u2026"):
        result = load_best_result(win, decomp, analysis_folder, rgcurve=rgcurve, xr_ranks=xr_ranks)
    if result is None:
        return
    show_mass(win, status_var, result, rgcurve=rgcurve, stage="Rigorous", heading=_heading(result))


class MassDialog:
    """The component table, the caveat, and the per-frame curve below."""

    COLUMNS = (("component", "Component", 90), ("rg", "Rg (\u00c5)", 90), ("mass", "Mass (kDa)", 110),
               ("note", "Note", 520))      # widths for 96 dpi, see dpi.px

    def __init__(self, win, rows, curve, curve_error, stage=None, heading=None):
        dlg = self._dlg = tk.Toplevel(win)
        dlg.title(window_title(stage))
        dlg.geometry(geometry(1000, 820))

        if heading:
            ttk.Label(dlg, text=heading).pack(anchor=tk.W, padx=8, pady=(8, 0))
        tree = ttk.Treeview(dlg, columns=[c for c, _, _ in self.COLUMNS], show="headings",
                            height=max(1, min(len(rows), 8)), selectmode="none")
        for key, title, width in self.COLUMNS:
            tree.heading(key, text=title)
            tree.column(key, width=px(width), anchor=tk.W if key == "note" else tk.CENTER)
        for row in rows:
            tree.insert("", tk.END, values=row)
        tree.pack(fill=tk.X, padx=8, pady=(8, 4))
        self._tree = tree

        # always visible, not a tooltip: a mass must not be read as an exact value
        ttk.Label(dlg, text=CAVEAT, wraplength=px(960), justify=tk.LEFT, foreground="#7a3b00").pack(
            fill=tk.X, padx=8, pady=4)

        figframe = ttk.Frame(dlg)
        figframe.pack(fill=tk.BOTH, expand=True)
        if curve is None:
            ttk.Label(figframe, text=f"The per-frame curve is not available: {curve_error}",
                      foreground="gray").pack(pady=20)
            self._fig = None
        else:
            from matplotlib.figure import Figure
            self._fig = Figure(figsize=(9.5, 4.2))
            ax = self._fig.add_subplot(111)
            curve.plot(ax=ax)
            ax.set_title("Volume-of-correlation mass and Rg along the elution")
            self._fig.tight_layout()
            embed_plot(figframe, self._fig)

        _close = self._close
        ttk.Button(dlg, text="Close", command=_close).pack(pady=8)
        dlg.protocol("WM_DELETE_WINDOW", _close)

    def _close(self):
        if self._fig is not None:
            close_dialog_figure(self._dlg, self._fig)
        else:
            self._dlg.destroy()
