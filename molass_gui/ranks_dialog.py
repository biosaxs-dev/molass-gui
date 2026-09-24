"""Set Ranks dialog -- optional per-component rank override (1=normal,
2=concentration-dependent/interparticle) for the currently-loaded result.

Ephemeral by design: kept only on the calling view (e.g. RigorousView's
self._xr_ranks), not written back to recipe.json -- rank-2 cases are rare
and usually noticed only after inspecting an already-optimized result, so
this is a diagnostic override, not a declared pipeline choice.
"""
import tkinter as tk
from tkinter import ttk


def show_set_ranks_lazy(win, num_components, current_ranks, on_apply):
    """Open a small dialog to set/override xr_ranks.

    Parameters
    ----------
    win : tk widget
        Parent window.
    num_components : int
        Expected length of the ranks list.
    current_ranks : list of int or None
        Pre-fills the entry; None shows the all-1 (default) list.
    on_apply : callable(list of int)
        Called with the validated ranks list when Apply is clicked.
    """
    dlg = tk.Toplevel(win)
    dlg.title("Set Ranks")
    dlg.resizable(False, False)

    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill=tk.BOTH, expand=True)
    ttk.Label(frm, text=f"Ranks for {num_components} component(s), comma-separated\n"
                        "(1 = normal, 2 = concentration-dependent/interparticle):").pack(
        anchor=tk.W)
    default = ",".join(str(r) for r in current_ranks) if current_ranks else \
        ",".join(["1"] * num_components)
    ranks_var = tk.StringVar(value=default)
    ttk.Entry(frm, textvariable=ranks_var, width=24).pack(pady=8, fill=tk.X)
    error_var = tk.StringVar(value="")
    ttk.Label(frm, textvariable=error_var, foreground="red").pack(anchor=tk.W)

    def _apply():
        text = ranks_var.get().strip()
        try:
            ranks = [int(x) for x in text.split(",")]
        except ValueError:
            error_var.set("Must be a comma-separated list of integers, e.g. 1,1,2")
            return
        if len(ranks) != num_components:
            error_var.set(f"Expected {num_components} value(s), got {len(ranks)}")
            return
        on_apply(ranks)
        dlg.destroy()

    btn_row = ttk.Frame(frm)
    btn_row.pack(pady=(4, 0))
    ttk.Button(btn_row, text="Apply", command=_apply, style="Accent.TButton").pack(
        side=tk.LEFT, padx=4)
    ttk.Button(btn_row, text="Cancel", command=dlg.destroy).pack(side=tk.LEFT, padx=4)
