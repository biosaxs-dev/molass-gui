"""Homogeneity dialog -- ratio curves of concentration proxies (I(0), I(q), A(wavelength)) across
the elution peaks, with descriptive statistics and no pure/impure verdict.

The selection of ratios is a matrix of check buttons (row = numerator, column = denominator),
filled by presets; the UV->XR mapping can be shifted to see which ratios depend on it.
Computation is ``SecSaxsData.homogeneity()`` (molass-library), cheap once the Rg curve exists.
"""
import tkinter as tk
from tkinter import ttk

from molass_gui.homogeneity_logic import (PRESETS, default_proxy_names, normalize_proxy_name, preset_pairs,
                                          pairs_from_matrix, parse_cores, format_cores)
from molass_gui.plot_embed import embed_plot, close_dialog_figure

_HELP = ("Ratio of two concentration proxies is flat across a peak of one species. XR-only ratios (size/shape) and "
         "UV-only ratios (spectrum) do not depend on the UV->XR mapping; XR/UV ratios (*) do: a mapping error "
         "gives a tilt, a concentration effect a curvature. Curves and statistics only - no verdict.")


def _with_i0(win, status_var, ssd, rgcurve, then):
    """Call ``then(rgcurve_with_i0)``. An Rg curve restored from disk (Open Existing Analysis) has no I(0):
    the Guinier fits (about 30 s) then run in a background thread first, with a status message."""
    import threading
    import numpy as np
    i0s = getattr(rgcurve, "i0s", None)
    if i0s is not None and np.isfinite(np.asarray(i0s, dtype=float)).any():
        then(rgcurve)
        return
    from molass.Homogeneity import ensure_i0_rgcurve
    prev = status_var.get()
    status_var.set("Computing I(0) from Guinier fits (about 30 s)\u2026")
    box = {}

    def worker():
        try:
            box["rg"] = ensure_i0_rgcurve(ssd, rgcurve)
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
            from molass_gui.error_dialog import show_error_detail
            show_error_detail(win, status_var, str(box["err"]), title="Homogeneity failed")
            return
        then(box["rg"])

    win.after(300, poll)


def show_homogeneity(win, status_var, ssd, rgcurve, optimized_mapping=None):
    """Open the Homogeneity dialog for the corrected ``ssd`` (needs the per-frame ``rgcurve`` for I(0)).

    ``optimized_mapping`` (see ``homogeneity_logic.optimized_mapping_of``) offers the mapping of
    optimized UV curves next to the estimated one."""
    def open_dialog(rg):
        prev = status_var.get()
        status_var.set("Computing homogeneity\u2026")
        win.update_idletasks()
        try:
            first = ssd.homogeneity(rgcurve=rg)
        finally:
            status_var.set(prev)
        HomogeneityDialog(win, ssd, rg, first, optimized_mapping=optimized_mapping)

    _with_i0(win, status_var, ssd, rgcurve, open_dialog)


def show_homogeneity_lazy(win, status_var, decomp, analysis_folder, rgcurve=None, xr_ranks=None):
    """Rigorous stage: load the best completed result from *analysis_folder* and open the Homogeneity
    dialog with the result's optimized UV->XR mapping offered next to the estimated one.

    Same job selection as Plot Components (the true global best, not just the latest).
    """
    from molass_gui.best_result import load_best_result

    prev = status_var.get()
    status_var.set("Loading current result\u2026")
    win.update_idletasks()
    try:
        result = load_best_result(win, decomp, analysis_folder, rgcurve=rgcurve, xr_ranks=xr_ranks)
        if result is None:
            return
        ssd = decomp.ssd
        optimized = result.get_uv_mapping() if ssd.uv is not None else None
    finally:
        status_var.set(prev)

    def open_dialog(rg):
        first = ssd.homogeneity(rgcurve=rg)
        HomogeneityDialog(win, ssd, rg, first, optimized_mapping=optimized)

    _with_i0(win, status_var, ssd, rgcurve, open_dialog)


class HomogeneityDialog:
    def __init__(self, win, ssd, rgcurve, first, optimized_mapping=None):
        self._ssd, self._rgcurve = ssd, rgcurve
        self._q1, self._q2 = first.q1, first.q2
        self._has_uv = ssd.uv is not None
        self._optimized = optimized_mapping
        self._auto_cores = list(first.cores)
        self._cores = list(first.cores)
        self._names = default_proxy_names(self._q1, self._q2, self._has_uv)
        self._plot_state = None
        self._busy = False

        dlg = self._dlg = tk.Toplevel(win)
        dlg.title("Homogeneity")
        dlg.geometry("1300x900")

        left = ttk.Frame(dlg, padding=8)
        left.pack(side=tk.LEFT, fill=tk.Y)
        right = ttk.Frame(dlg)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._map_var = tk.StringVar(master=dlg, value="optimized" if optimized_mapping is not None else "estimated")
        if optimized_mapping is not None and self._has_uv:
            from molass.Homogeneity import mapping_shift
            centers = [(a + b) / 2 for a, b in self._cores]
            shifts = mapping_shift(ssd.get_mapping(), optimized_mapping, centers)
            info = "; ".join(f"{s:+.2f} at frame {c:.0f}" for s, c in zip(shifts, centers))
            ttk.Label(left, text="UV->XR mapping:").pack(anchor=tk.W)
            ttk.Radiobutton(left, text="Estimated (quick)", variable=self._map_var, value="estimated",
                            command=self._recompute).pack(anchor=tk.W, padx=12)
            ttk.Radiobutton(left, text="Optimized (rigorous)", variable=self._map_var, value="optimized",
                            command=self._recompute).pack(anchor=tk.W, padx=12)
            ttk.Label(left, text=f"optimized vs estimated, equivalent shift in XR frames: {info}",
                      foreground="gray", wraplength=300, justify=tk.LEFT).pack(anchor=tk.W, pady=(2, 8))

        ttk.Label(left, text="Ratio set:").pack(anchor=tk.W)
        self._preset_var = tk.StringVar(master=dlg, value="Default")
        cb = ttk.Combobox(left, textvariable=self._preset_var, values=PRESETS, state="readonly", width=26)
        cb.pack(anchor=tk.W, pady=(0, 6))
        cb.bind("<<ComboboxSelected>>", lambda _e: self._apply_preset())

        ttk.Label(left, text="Numerator (row) / denominator (column):").pack(anchor=tk.W)
        self._matrix_frame = ttk.Frame(left)
        self._matrix_frame.pack(anchor=tk.W, pady=(0, 6))
        self._vars = {}
        self._build_matrix()

        row = ttk.Frame(left)
        row.pack(anchor=tk.W, pady=2)
        ttk.Label(row, text="Add proxy:").pack(side=tk.LEFT)
        self._add_var = tk.StringVar(master=dlg, value="")
        e = ttk.Entry(row, textvariable=self._add_var, width=10)
        e.pack(side=tk.LEFT, padx=4)
        e.bind("<Return>", lambda _e: self._add_proxy())
        ttk.Button(row, text="Add", command=self._add_proxy).pack(side=tk.LEFT)
        ttk.Label(left, text="e.g. I(0.03), A250", foreground="gray").pack(anchor=tk.W)

        if self._has_uv:
            ttk.Label(left, text="\nExtra shift on top of the mapping (frames, + = later):").pack(anchor=tk.W)
            self._delta_var = tk.DoubleVar(master=dlg, value=0.0)
            self._delta_text = tk.StringVar(master=dlg, value="+0.00")
            srow = ttk.Frame(left)
            srow.pack(anchor=tk.W, fill=tk.X)
            scale = ttk.Scale(srow, from_=-3.0, to=3.0, variable=self._delta_var, length=200,
                              command=lambda v: self._delta_text.set(f"{float(v):+.2f}"))
            scale.pack(side=tk.LEFT)
            scale.bind("<ButtonRelease-1>", lambda _e: self._recompute())
            ttk.Label(srow, textvariable=self._delta_text, width=6).pack(side=tk.LEFT, padx=4)
            ttk.Button(srow, text="Reset", command=self._reset_delta).pack(side=tk.LEFT)
        else:
            self._delta_var = tk.DoubleVar(master=dlg, value=0.0)

        ttk.Label(left, text="\nPeak cores (first-last frame):").pack(anchor=tk.W)
        self._cores_var = tk.StringVar(master=dlg, value=format_cores(self._cores))
        crow = ttk.Frame(left)
        crow.pack(anchor=tk.W)
        ttk.Entry(crow, textvariable=self._cores_var, width=22).pack(side=tk.LEFT)
        ttk.Button(crow, text="Apply", command=self._apply_cores).pack(side=tk.LEFT, padx=4)
        ttk.Button(crow, text="Auto", command=self._auto_cores_reset).pack(side=tk.LEFT)

        self._status_var = tk.StringVar(master=dlg, value="")
        ttk.Label(left, textvariable=self._status_var, foreground="firebrick", wraplength=300).pack(anchor=tk.W, pady=6)
        ttk.Label(left, text=_HELP, foreground="gray", wraplength=300, justify=tk.LEFT).pack(anchor=tk.W, pady=6)
        ttk.Button(left, text="Close", command=self._close).pack(side=tk.BOTTOM, pady=4)

        self._plot_frame = ttk.Frame(right)
        self._plot_frame.pack(fill=tk.BOTH, expand=True)
        text_frame = ttk.Frame(right)
        text_frame.pack(fill=tk.X)
        self._text = tk.Text(text_frame, height=13, font=("Consolas", 9), wrap="none")
        sb = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self._text.yview)
        self._text.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._text.pack(side=tk.LEFT, fill=tk.X, expand=True)
        dlg.protocol("WM_DELETE_WINDOW", self._close)

        self._set_matrix(preset_pairs("Default", self._names, self._q1, self._q2, self._has_uv))
        self._recompute()

    # -- matrix of checkbuttons ------------------------------------------------------------
    def _build_matrix(self):
        for w in self._matrix_frame.winfo_children():
            w.destroy()
        old = {k: v.get() for k, v in self._vars.items()}
        self._vars = {}
        for j, den in enumerate(self._names):
            ttk.Label(self._matrix_frame, text=den, font=("TkDefaultFont", 8)).grid(row=0, column=j + 1, padx=1)
        for i, num in enumerate(self._names):
            ttk.Label(self._matrix_frame, text=num, font=("TkDefaultFont", 8)).grid(row=i + 1, column=0, sticky=tk.E)
            for j, den in enumerate(self._names):
                if i == j:
                    continue
                var = tk.BooleanVar(master=self._dlg, value=old.get((num, den), False))
                self._vars[(num, den)] = var
                ttk.Checkbutton(self._matrix_frame, variable=var,
                                command=self._on_matrix_change).grid(row=i + 1, column=j + 1)

    def _set_matrix(self, pairs):
        on = set(pairs)
        for key, var in self._vars.items():
            var.set(key in on)

    def _selected_pairs(self):
        return pairs_from_matrix({k: v.get() for k, v in self._vars.items()})

    def _on_matrix_change(self):
        self._preset_var.set("Custom")
        self._recompute()

    def _apply_preset(self):
        self._set_matrix(preset_pairs(self._preset_var.get(), self._names, self._q1, self._q2, self._has_uv))
        self._recompute()

    def _add_proxy(self):
        text = self._add_var.get()
        if not text.strip():
            return
        try:
            name = normalize_proxy_name(text)
        except ValueError as exc:
            self._status_var.set(str(exc))
            return
        if name.startswith("A") and not self._has_uv:
            self._status_var.set("This data has no UV part")
            return
        if name not in self._names:
            self._names.append(name)
            self._build_matrix()
        self._add_var.set("")
        self._status_var.set("")

    # -- shift and cores -------------------------------------------------------------------
    def _reset_delta(self):
        self._delta_var.set(0.0)
        self._delta_text.set("+0.00")
        self._recompute()

    def _apply_cores(self):
        try:
            self._cores = parse_cores(self._cores_var.get())
        except ValueError as exc:
            self._status_var.set(str(exc))
            return
        self._recompute()

    def _auto_cores_reset(self):
        self._cores = list(self._auto_cores)
        self._cores_var.set(format_cores(self._cores))
        self._recompute()

    # -- computation and drawing -----------------------------------------------------------
    def _recompute(self):
        if self._busy:
            return
        pairs = self._selected_pairs()
        if not pairs:
            self._status_var.set("Select at least one ratio")
            return
        self._busy = True
        try:
            mapping = self._optimized if self._map_var.get() == "optimized" else None
            result = self._ssd.homogeneity(pairs=pairs, delta=round(float(self._delta_var.get()), 2), q1=self._q1,
                                           q2=self._q2, cores=self._cores, rgcurve=self._rgcurve, mapping=mapping)
            self._status_var.set("; ".join(result.skipped))
            fig = result.plot(figsize=(9, 6))
            kind = "optimized" if mapping is not None else "estimated"
            fig.axes[1].set_title(f"* depends on the UV->XR mapping ({kind}, extra shift {result.delta:+g} frame); "
                                  f"{result.independent_axes} independent axes", fontsize=9)
            self._plot_state = embed_plot(self._plot_frame, fig, previous=self._plot_state)
            self._text.configure(state="normal")
            self._text.delete("1.0", tk.END)
            self._text.insert("1.0", f"mapping: {kind}\n" + result.summary())
            self._text.configure(state="disabled")
        except Exception as exc:
            self._status_var.set(f"{type(exc).__name__}: {exc}")
        finally:
            self._busy = False

    def _close(self):
        fig = self._plot_state[2] if self._plot_state else None
        if fig is not None:
            close_dialog_figure(self._dlg, fig)
        else:
            self._dlg.destroy()
