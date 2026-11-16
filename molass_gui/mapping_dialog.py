"""Mapping dialog -- how the UV frames are related to the X-ray frames, and whether to believe it.

Shows the mapping the session's trimming rests on (``trimmed.trimming.mapping``): the line ``UV frame = a x XR
frame + b`` with the plausibility numbers the library computes, the UV curve carried onto the XR frame axis over the
XR curve (a mismatched peak pairing is visible at a glance), and the matched peak pairs with the fitted line (the
points the regression used, so the linear assumption can be judged by eye). Nothing is computed here beyond
drawing: everything comes from the ``MappingInfo``, so the dialog opens at once.
"""
import tkinter as tk
from tkinter import ttk

import numpy as np

from molass_gui import busy
from molass_gui.plot_embed import close_dialog_figure
from molass_gui.window_tree import register_window_cleanup

WINDOW_TITLE = "Mapping"
FIGURE_SIZE = (11.0, 4.6)       # inches, at the figure.dpi of the session


def mapping_texts(mapping):
    """The lines above the figure: ``(equation, numbers, verdict, plausible)``. Pure, no Tk."""
    sign = "-" if mapping.intercept < 0 else "+"
    equation = "UV frame = %.4g \u00d7 XR frame %s %.4g" % (mapping.slope, sign, abs(mapping.intercept))

    parts = []
    quality = mapping.quality
    if not np.isnan(quality.correlation):
        parts.append("shape correlation %.2f" % quality.correlation)
    if not np.isnan(quality.coverage):
        parts.append("coverage %.2f" % quality.coverage)
    resolution = getattr(mapping, "resolution_frames", None)
    if resolution is not None:
        parts.append("uncertainty about %.2g XR frame%s (noise only)" % (resolution, "" if resolution == 1 else "s"))
    n_peaks = len(mapping.xr_peaks)
    if n_peaks == 1:
        parts.append("one peak: from its mean and width only, much less certain")
    else:
        parts.append("%d matched peaks" % n_peaks)
    numbers = "  |  ".join(parts)

    plausible = bool(mapping.is_plausible())
    verdict = ("plausible" if plausible
               else "implausible: the UV curve does not follow the XR curve under this mapping; check the overlay")
    return equation, numbers, verdict, plausible


def pair_points(mapping):
    """The points the line was fitted through, ``(xr_frames, uv_frames)``: the matched peaks, or for a single
    peak the mean and mean \u00b1 width of each curve. Pure, no Tk."""
    if len(mapping.xr_peaks) == 1 and mapping.xr_moment is not None and mapping.uv_moment is not None:
        xr_m, xr_s = mapping.xr_moment.get_meanstd()
        uv_m, uv_s = mapping.uv_moment.get_meanstd()
        return (np.array([xr_m - xr_s, xr_m, xr_m + xr_s]), np.array([uv_m - uv_s, uv_m, uv_m + uv_s]))
    return np.asarray(mapping.xr_peak_frames, dtype=float), np.asarray(mapping.uv_peak_frames, dtype=float)


def kept_xr_frames(trimming):
    """The XR frame range the trimming kept, ``(first, last)``, or None when it cannot be told. Pure, no Tk."""
    try:
        jslice = trimming.xr_slices[1]
        if jslice is None:
            return None
        x = np.asarray(trimming.mapping.xr_curve.x, dtype=float)
        start, stop, _ = jslice.indices(len(x))
        return float(x[start]), float(x[stop - 1])
    except Exception:
        return None


def make_figure(mapping, trimming=None):
    """The overlay (left) and the peak pairs with the fitted line (right) as a Figure (no pyplot)."""
    from matplotlib.figure import Figure
    import matplotlib

    fig = Figure(figsize=FIGURE_SIZE, dpi=matplotlib.rcParams["figure.dpi"])
    ax_overlay, ax_pairs = fig.subplots(1, 2)

    xr_x, xr_y = np.asarray(mapping.xr_curve.x, dtype=float), np.asarray(mapping.xr_curve.y, dtype=float)
    uv_x, uv_y = np.asarray(mapping.uv_curve.x, dtype=float), np.asarray(mapping.uv_curve.y, dtype=float)
    mapped_x = mapping.uv_to_xr(uv_x)

    ax_overlay.set_title("Overlay: UV mapped onto the XR frame axis")
    ax_overlay.plot(xr_x, xr_y, color="C1", label="XR")
    ax_overlay.set_xlabel("XR frame")
    ax_overlay.set_ylabel("XR intensity", color="C1")
    ax_uv = ax_overlay.twinx()
    ax_uv.plot(mapped_x, uv_y, color="C0", alpha=0.7, label="UV (mapped)")
    ax_uv.set_ylabel("UV absorbance", color="C0")
    for k, (xp, up) in enumerate(zip(np.asarray(mapping.xr_peaks, dtype=int), np.asarray(mapping.uv_peaks, dtype=int))):
        ax_overlay.plot(xr_x[xp], xr_y[xp], "o", color="C1")
        ax_uv.plot(mapped_x[up], uv_y[up], "o", color="C0")
        ax_overlay.annotate(str(k), (xr_x[xp], xr_y[xp]), textcoords="offset points", xytext=(0, 6), ha="center")
    handles = ax_overlay.get_lines()[:1] + ax_uv.get_lines()[:1]
    ax_overlay.legend(handles, ["XR", "UV (mapped)"], loc="center left")

    ax_pairs.set_title("Peak pairs and the fitted line")
    ax_pairs.set_xlabel("XR frame")
    ax_pairs.set_ylabel("UV frame")
    ax_pairs.plot(xr_x[[0, -1]], mapping.xr_to_uv(xr_x[[0, -1]]), color="gray", label="UV = a \u00d7 XR + b")
    px, py = pair_points(mapping)
    ax_pairs.plot(px, py, "o", color="C3",
                  label="matched peaks" if len(mapping.xr_peaks) > 1 else "mean and mean \u00b1 width")
    kept = None if trimming is None else kept_xr_frames(trimming)
    if kept is not None:
        ax_pairs.axvspan(kept[0], kept[1], color="green", alpha=0.1, label="XR frames kept by the trimming")
    ax_pairs.legend(loc="upper left")

    fig.tight_layout()
    return fig


def show_mapping(win, status_var, trimmed, previous=None):
    """Open the dialog (a Toplevel of *win*) and return it.

    *trimmed* is the session's ``trimmed_copy()``. When *previous* (the dialog returned by an earlier call) is
    still open it is raised instead of building the figure again. Returns None, after telling the user, when
    there is no mapping to draw.
    """
    if previous is not None and _exists(previous):
        previous.deiconify()
        previous.lift()
        return previous

    from molass_gui.error_dialog import show_error_detail
    trimming = getattr(trimmed, "trimming", None)
    mapping = getattr(trimming, "mapping", None)
    if mapping is None:
        show_error_detail(win, status_var, "This data has no UV/XR mapping to draw (a single-channel data set).",
                          title="Mapping unavailable")
        return None
    try:
        with busy.working(win, status_var, "Drawing the mapping\u2026", key="mapping"):
            texts = mapping_texts(mapping)
            fig = make_figure(mapping, trimming)
    except Exception as exc:
        show_error_detail(win, status_var, str(exc), title="Mapping plot failed")
        return None

    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
    equation, numbers, verdict, plausible = texts
    dlg = tk.Toplevel(win)
    dlg.title(WINDOW_TITLE)
    header = ttk.Frame(dlg, padding=(10, 8, 10, 0))
    header.pack(side=tk.TOP, fill=tk.X)
    ttk.Label(header, text=equation, font=("", 11, "bold")).pack(anchor=tk.W)
    ttk.Label(header, text=numbers, foreground="#555").pack(anchor=tk.W)
    ttk.Label(header, text=verdict, foreground="#15803d" if plausible else "#b91c1c").pack(anchor=tk.W)

    _close = lambda: close_dialog_figure(dlg, fig)
    ttk.Button(dlg, text="Close", command=_close).pack(side=tk.BOTTOM, pady=8)
    toolbar_row = ttk.Frame(dlg)
    toolbar_row.pack(side=tk.BOTTOM, fill=tk.X)
    canvas = FigureCanvasTkAgg(fig, master=dlg)
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
