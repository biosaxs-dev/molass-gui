"""Scoped window-close and window-visibility helpers shared across all phase views.

Two independent close-related concerns per window:
  - cleanup: things that must run before the window (and its descendants) are
    destroyed, e.g. stopping a live optimizer run.
  - close guard: a predicate that reports whether closing right now would
    interrupt something long-running (e.g. an active rigorous optimization),
    used to show a confirmation dialog before proceeding.

Both are scoped to a window and its descendant Toplevels, mirroring the
Tkinter parent/child hierarchy that already matches the phase hierarchy
(NaiveView -> QuickView -> UpgradedView -> RigorousView). This lets
"Close Session" (the whole app) and "Close Model" (just UpgradedView +
RigorousView) share the same mechanism -- "Close Session" is simply this
mechanism applied to the root window.
"""
import tkinter as tk
from tkinter import messagebox


def register_window_cleanup(win, fn):
    """Attach a cleanup callback to *win*, run (once) when win or an ancestor
    of win is closed via close_window()/confirm_and_close()."""
    win._cleanups = getattr(win, '_cleanups', []) + [fn]


def register_close_guard(win, predicate, message):
    """Attach a close guard to *win*.

    predicate : callable() -> bool
        Returns True if closing right now would interrupt something ongoing.
    message : str
        Shown in the confirmation dialog if the predicate is True.
    """
    win._close_guards = getattr(win, '_close_guards', []) + [(predicate, message)]


def _descendant_toplevels(win):
    return [c for c in win.winfo_children() if isinstance(c, tk.Toplevel)]


def collect_close_warnings(win):
    """Recursively collect close-guard messages currently active for *win*
    and all its descendant Toplevels."""
    warnings = []
    for child in _descendant_toplevels(win):
        warnings.extend(collect_close_warnings(child))
    for predicate, message in getattr(win, '_close_guards', []):
        try:
            if predicate():
                warnings.append(message)
        except Exception:
            pass
    return warnings


def close_window(win):
    """Run cleanups for *win* and all descendant Toplevels (deepest first),
    then destroy the whole subtree. No confirmation -- see confirm_and_close."""
    for child in _descendant_toplevels(win):
        close_window(child)
    for fn in getattr(win, '_cleanups', []):
        try:
            fn()
        except Exception:
            pass
    win.destroy()


def confirm_and_close(win):
    """Show a confirmation dialog if closing *win* would interrupt anything
    guarded (in win or a descendant), then close_window(win) if confirmed.

    Returns True if the window was actually closed, False if the user
    cancelled.
    """
    warnings = collect_close_warnings(win)
    if warnings:
        msg = ("Closing will stop the following in-progress work:\n\n"
               + "\n".join(f"\u2022 {w}" for w in warnings)
               + "\n\nContinue?")
        if not messagebox.askyesno("Confirm Close", msg, icon='warning', parent=win):
            return False
    close_window(win)
    return True
