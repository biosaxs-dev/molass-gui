"""Shared helper for embedding a matplotlib figure into a Tk window, and replacing an
already-embedded plot in place (e.g. once a background computation like the Rg curve
becomes ready and the figure needs to be redrawn with it overlaid)."""
import gc
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
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
        # plt.close() alone leaves the old Figure/Axes/canvas objects alive until
        # the next cyclic GC pass (reference cycles) -- if that pass is triggered
        # by allocations on a background thread (e.g. optimize_rigorously()'s
        # legacy pipeline), the deferred Tk widget teardown runs off the main
        # thread and crashes the process (Tcl_AsyncDelete). Force it here,
        # deterministically, on the main thread -- same fix molass-legacy's
        # Dialog.destroy() applies for the same reason (OurTkinter.py).
        gc.collect()

    canvas = FigureCanvasTkAgg(fig, master=win)
    canvas.draw()
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    toolbar = NavigationToolbar2Tk(canvas, win)
    toolbar.update()
    return canvas, toolbar, fig


def close_dialog_figure(dlg, fig):
    """Close *fig* and force GC before destroying *dlg* -- same rationale as
    embed_plot()'s gc.collect(): a bare dlg.destroy() leaves the Figure/Axes/
    canvas object graph (reference cycles) alive until whatever thread next
    triggers a cyclic GC pass, risking a Tk teardown off the main thread."""
    plt.close(fig)
    gc.collect()
    dlg.destroy()


_last_export_format = 'dat'


def ask_export_options(parent_win):
    """Modal dialog: choose the file format, then the destination folder.

    Returns ``(folder, fmt)``, or None if cancelled. The last format used is
    preselected on the next call.
    """
    global _last_export_format
    result = {}

    dlg = tk.Toplevel(parent_win)
    dlg.title("Export Data")
    dlg.transient(parent_win)
    fmt_var = tk.StringVar(master=dlg, value=_last_export_format)

    frame = ttk.Frame(dlg, padding=12)
    frame.pack(fill=tk.BOTH, expand=True)
    ttk.Label(frame, text="File format:").pack(anchor=tk.W)
    ttk.Radiobutton(frame, text=".dat  (whitespace-delimited, '# ' header; np.loadtxt, IGOR)",
                    variable=fmt_var, value='dat').pack(anchor=tk.W, padx=12)
    ttk.Radiobutton(frame, text=".csv  (comma-delimited, header row; Excel, pandas)",
                    variable=fmt_var, value='csv').pack(anchor=tk.W, padx=12)

    def _choose():
        folder = filedialog.askdirectory(title="Select export folder", parent=dlg)
        if folder:
            result['value'] = (folder, fmt_var.get())
            dlg.destroy()

    row = ttk.Frame(frame)
    row.pack(pady=(12, 0))
    ttk.Button(row, text="Choose Folder\u2026", command=_choose).pack(side=tk.LEFT, padx=4)
    ttk.Button(row, text="Cancel", command=dlg.destroy).pack(side=tk.LEFT, padx=4)

    dlg.grab_set()
    dlg.wait_window()
    if 'value' not in result:
        return None
    _last_export_format = result['value'][1]
    return result['value']


def export_component_data(result, parent_win, rgcurve=None):
    """Export the decomposition shown in the view to a user-chosen folder.

    Works with a plain Decomposition (QuickView/UpgradedView) or a rigorous
    result (Plot Components dialog). Delegates the file-writing to
    ``Decomposition.export()`` -- component profiles plus elution curves, UV,
    Guinier results, the Rg curve and a summary.json (molass-library#319) --
    so the GUI and scripts/notebooks share one implementation. *rgcurve* is
    the Rg curve the view already computed, so it is written without
    recomputation. Older molass versions without ``export()`` fall back to
    ``export_xr_components()`` (component profiles only, always ``.dat``).
    """
    options = ask_export_options(parent_win)
    if options is None:
        return
    folder, fmt = options

    try:
        if hasattr(result, 'export'):
            paths = result.export(folder, fmt=fmt, rgcurve=rgcurve)
            message = f"Exported {len(paths)} file(s) to:\n{folder}"
        else:
            paths = result.export_xr_components(folder)
            message = f"Exported {len(paths)} component curve(s) to:\n{folder}"
    except Exception as exc:
        messagebox.showerror("Export failed", str(exc), parent=parent_win)
        return

    messagebox.showinfo("Export complete", message, parent=parent_win)

