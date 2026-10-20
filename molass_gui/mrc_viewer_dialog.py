"""MRC viewer dialog -- shows an electron-density (.mrc) file, e.g. a DENSS result.

The figure itself (isosurface / voxel scatter switch, slices, density histogram)
is built by ``molass.SAXS.MrcViewer.make_mrc_figure`` so that a notebook can
reproduce exactly what this dialog shows with ``show_mrc_views(path)``.
"""
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from molass_gui.plot_embed import embed_plot, close_dialog_figure


class MrcViewerDialog:
    def __init__(self, parent, mrc_path):
        self._plot = None       # (canvas, toolbar, fig) of the embedded figure
        self._mrc_path = None

        win = tk.Toplevel(parent)
        win.title("MRC Viewer")
        self._win = win

        top = ttk.Frame(win, padding=(8, 8, 8, 0))
        top.pack(fill=tk.X)
        self._path_var = tk.StringVar(value="")
        ttk.Label(top, textvariable=self._path_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(top, text="Open\u2026", command=self._open_other).pack(side=tk.RIGHT)

        self._plot_frame = ttk.Frame(win)
        self._plot_frame.pack(fill=tk.BOTH, expand=True)

        btn_row = ttk.Frame(win, padding=8)
        btn_row.pack()
        ttk.Button(btn_row, text="Close", command=self._close).pack()
        win.protocol("WM_DELETE_WINDOW", self._close)

        self._load(mrc_path)

    def _load(self, mrc_path):
        from matplotlib.figure import Figure
        from molass.SAXS.MrcViewer import make_mrc_figure

        self._win.configure(cursor="watch")
        self._path_var.set(f"Loading {mrc_path} \u2026")
        self._win.update_idletasks()
        try:
            self._stop_timer()
            fig = make_mrc_figure(mrc_path, fig=Figure(figsize=(12, 5.5)))
        except Exception as exc:
            self._path_var.set(self._mrc_path or "")
            messagebox.showerror("Cannot show MRC file", f"{mrc_path}\n\n{exc}", parent=self._win)
            return
        finally:
            self._win.configure(cursor="")
        self._plot = embed_plot(self._plot_frame, fig, previous=self._plot)
        self._mrc_path = mrc_path
        self._path_var.set(mrc_path)

    def _open_other(self):
        initial = os.path.dirname(self._mrc_path) if self._mrc_path else None
        path = filedialog.askopenfilename(title="Select an MRC file", initialdir=initial,
                                          filetypes=[("MRC files", "*.mrc"), ("All files", "*.*")],
                                          parent=self._win)
        if path:
            self._load(path)

    def _stop_timer(self):
        # the auto-rotate timer must not outlive its figure
        if self._plot is not None:
            timer = self._plot[2]._mrc_viewer_state[0]["timer"]
            if timer is not None:
                timer.stop()

    def _close(self):
        self._stop_timer()
        fig = self._plot[2] if self._plot is not None else None
        self._plot = None
        if fig is not None:
            close_dialog_figure(self._win, fig)
        else:
            self._win.destroy()


def show_mrc_viewer(parent, mrc_path):
    """Open the MRC viewer dialog on *mrc_path*."""
    return MrcViewerDialog(parent, mrc_path)
