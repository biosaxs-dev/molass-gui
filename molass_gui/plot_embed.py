"""Shared helper for embedding a matplotlib figure into a Tk window, and replacing an
already-embedded plot in place (e.g. once a background computation like the Rg curve
becomes ready and the figure needs to be redrawn with it overlaid)."""
import tkinter as tk
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
