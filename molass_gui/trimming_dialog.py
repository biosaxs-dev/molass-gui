"""Trimming dialog -- what the trimming cut away, on the entire (untrimmed) data.

Shows ``SecSaxsData.plot_trimming()``: for UV and XR, the whole data matrix with the kept region shaded, the
elution curve with the kept frames and the spectral/scattering curve with the kept range (with the peak frame
of one channel carried to the other by the mapping). The figure is drawn for the trimming the session actually
used (``trimmed.trimming``), not for a fresh default one, so it also tells the effect of the Load dialog's
small-angle choice.
"""
import tkinter as tk
from tkinter import ttk

from molass_gui import busy, dpi
from molass_gui.plot_embed import close_dialog_figure
from molass_gui.window_tree import register_window_cleanup

# window size designed at 96 dpi: the figure's width (plot_trimming() makes a 16 x 8 inch figure, too big for
# a dialog as it is) and the height the toolbar and the Close button need below it
WINDOW_WIDTH = 1250
TOOLBAR_AND_BUTTON = 90
WINDOW_TITLE = "Trimming"


def show_trimming(win, status_var, ssd, trimmed, previous=None):
    """Open the dialog (a Toplevel of *win*) and return it.

    *ssd* is the entire data and *trimmed* its ``trimmed_copy()``. When *previous* (the dialog returned by an
    earlier call) is still open it is raised instead of building the figure again. Returns None, after telling
    the user, when the trimming cannot be drawn.
    """
    if previous is not None and _exists(previous):
        previous.deiconify()
        previous.lift()
        return previous

    from molass_gui.error_dialog import show_error_detail
    trimming = getattr(trimmed, "trimming", None)
    if trimming is None:
        show_error_detail(win, status_var, "This data has no trimming information to draw.",
                          title="Trimming unavailable")
        return None
    try:
        with busy.working(win, status_var, "Drawing the trimming\u2026", key="trimming"):
            fig = ssd.plot_trimming(trim=trimming).fig
    except Exception as exc:
        show_error_detail(win, status_var, str(exc), title="Trimming plot failed")
        return None

    # Fit the window by lowering the dpi, not by resizing the figure: the layout plot_trimming() has already
    # computed (tight_layout) stays valid, so it is not computed again, and the window can be given the
    # figure's pixel size at once instead of being drawn at one size and redrawn at another.
    width_px = dpi.px(WINDOW_WIDTH)
    fig.set_dpi(width_px / fig.get_figwidth())
    height_px = int(round(fig.get_figheight() * fig.dpi))

    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
    dlg = tk.Toplevel(win)
    dlg.title(WINDOW_TITLE)
    dlg.geometry("%dx%d" % (width_px, height_px + dpi.px(TOOLBAR_AND_BUTTON)))
    _close = lambda: close_dialog_figure(dlg, fig)
    ttk.Button(dlg, text="Close", command=_close).pack(side=tk.BOTTOM, pady=8)
    toolbar_row = ttk.Frame(dlg)
    toolbar_row.pack(side=tk.BOTTOM, fill=tk.X)
    canvas = FigureCanvasTkAgg(fig, master=dlg)        # drawn when the window is mapped, not before
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    NavigationToolbar2Tk(canvas, toolbar_row).update()
    dlg.protocol("WM_DELETE_WINDOW", _close)
    # the whole session closing destroys this Toplevel without close_dialog_figure: the figure must still be closed
    register_window_cleanup(dlg, lambda: _close_figure(fig))
    return dlg


def _exists(dlg):
    try:
        return bool(dlg.winfo_exists())
    except tk.TclError:
        return False


def _close_figure(fig):
    import gc
    import matplotlib.pyplot as plt
    plt.close(fig)
    gc.collect()
