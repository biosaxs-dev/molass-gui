"""Shared helper for embedding a matplotlib figure into a Tk window, and replacing an
already-embedded plot in place (e.g. once a background computation like the Rg curve
becomes ready and the figure needs to be redrawn with it overlaid)."""
import os
import tkinter as tk
from tkinter import filedialog, messagebox
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk


def embed_plot(win, fig, previous=None):
    """Pack *fig* into *win*, destroying the *previous* (canvas, toolbar, fig) tuple
    (as returned by an earlier call) if given. Returns the new (canvas, toolbar, fig)."""
    if previous is not None:
        old_canvas, old_toolbar, old_fig = previous
        old_toolbar.destroy()
        old_canvas.get_tk_widget().destroy()
        plt.close(old_fig)

    canvas = FigureCanvasTkAgg(fig, master=win)
    canvas.draw()
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    toolbar = NavigationToolbar2Tk(canvas, win)
    toolbar.update()
    return canvas, toolbar, fig


def export_component_data(result, parent_win):
    """Write each XR component's jcurve array to '<folder>/component_{i+1}.dat'.

    Works with any object exposing get_xr_components() -- a plain Decomposition
    (QuickView/UpgradedView) or a rigorous result (Plot Components dialog).

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

