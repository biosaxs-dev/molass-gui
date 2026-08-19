"""Show Parameters dialog -- read-only ttk.Treeview view of a rigorous optimizer's
parameter vector, built from molass.Rigorous.build_params_table().

Snapshot-only (per molass-gui architecture decision): built once when the dialog is
opened, not live-refreshing -- avoids re-running the optimizer's objective function
on a timer, which would reintroduce the class of Tk-threading risk already found
and fixed elsewhere in this app (see rigorous_view.py history).
"""
import tkinter as tk
from tkinter import ttk

from molass.Rigorous import build_params_table

_PER_COMPONENT_SECTIONS = ('xr', 'uv')


def show_params_dialog(parent, optimizer, params, title="Parameters"):
    """Build and display the parameter table for the given optimizer/params.

    Parameters
    ----------
    parent : tk widget
    optimizer :
        A rigorous optimizer, e.g. ``Score.optimizer``.
    params : array-like
        The parameter vector to display, e.g. ``Score.init_params`` or
        ``RunInfo.best_params``.
    title : str
    """
    df = build_params_table(optimizer, params)

    win = tk.Toplevel(parent)
    win.title(title)
    win.geometry("700x600")

    per_comp = df[df["section"].isin(_PER_COMPONENT_SECTIONS)]
    scalar = df[~df["section"].isin(_PER_COMPONENT_SECTIONS)]

    ttk.Label(win, text="Per-component parameters", font=("", 10, "bold")).pack(
        anchor="w", padx=8, pady=(8, 2))
    _build_per_component_tree(win, per_comp)

    ttk.Label(win, text="Shared / baseline parameters", font=("", 10, "bold")).pack(
        anchor="w", padx=8, pady=(12, 2))
    _build_scalar_tree(win, scalar)

    ttk.Button(win, text="Close", command=win.destroy).pack(pady=8)


def show_parameters_lazy(view, win, status_var, decomp, trimmed, params=None):
    """Ensure view._score exists (building it synchronously on first use, with a
    status message during the build), then open the params dialog.

    The build runs on the caller's thread -- expected to be the Tk main thread --
    and blocks the GUI for its duration; score() construction is not safe to run
    off the main thread (see rigorous_view.py's _prep_main docstring).

    Parameters
    ----------
    view : QuickView, UpgradedView, or RigorousView
        Holds/caches ``_score`` across repeated calls in the same view.
    win : tk widget
        Parent window for the status update and the dialog.
    status_var : tk.StringVar
        Temporarily shows "Building optimizer..." during a first-time build.
    decomp : Decomposition
    trimmed : SecSaxsData
    params : array-like, optional
        Parameter vector to display. Defaults to ``view._score.init_params``.
        Pass e.g. ``run_info.best_params`` to show the current/best values.
    """
    if getattr(view, '_score', None) is None:
        prev = status_var.get()
        status_var.set("Building optimizer\u2026")
        win.update_idletasks()
        try:
            view._score = decomp.score(trimmed_ssd=trimmed)
        finally:
            status_var.set(prev)
    score = view._score
    p = params if params is not None else score.init_params
    show_params_dialog(win, score.optimizer, p, title="Parameters")


def _build_per_component_tree(win, df):
    components = sorted(int(c) for c in df["component"].dropna().unique())
    columns = [f"comp_{c}" for c in components]

    frame = ttk.Frame(win)
    frame.pack(fill=tk.BOTH, expand=True, padx=8)
    tree = ttk.Treeview(frame, columns=columns, show="tree headings", height=12)
    tree.heading("#0", text="Section / Label")
    tree.column("#0", width=160)
    for c, col in zip(components, columns):
        tree.heading(col, text=f"Comp {c}")
        tree.column(col, width=100, anchor="e")

    vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    vsb.pack(side=tk.RIGHT, fill=tk.Y)

    for section in df["section"].unique():
        section_id = tree.insert("", "end", text=section, open=True)
        section_df = df[df["section"] == section]
        for label in section_df["label"].unique():
            row = section_df[section_df["label"] == label]
            values = []
            for c in components:
                match = row[row["component"] == c]
                values.append(f"{match['value'].iloc[0]:.4g}" if len(match) else "")
            tree.insert(section_id, "end", text=label, values=values)


def _build_scalar_tree(win, df):
    frame = ttk.Frame(win)
    frame.pack(fill=tk.BOTH, expand=False, padx=8, pady=(0, 8))
    tree = ttk.Treeview(frame, columns=("value",), show="tree headings", height=8)
    tree.heading("#0", text="Section / Label")
    tree.column("#0", width=160)
    tree.heading("value", text="Value")
    tree.column("value", width=120, anchor="e")

    vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    vsb.pack(side=tk.RIGHT, fill=tk.Y)

    for section in df["section"].unique():
        section_id = tree.insert("", "end", text=section, open=True)
        section_df = df[df["section"] == section]
        for _, row in section_df.iterrows():
            tree.insert(section_id, "end", text=row["label"], values=(f"{row['value']:.6g}",))
