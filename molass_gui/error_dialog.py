"""Shared error-detail dialog.

Background worker threads across this app (naive_view/quick_view/app "Load")
report failures by setting a status ``tk.StringVar`` shown inline in the
window's header row. That pattern breaks down for long messages (e.g.
molass-library's degenerate-decomposition RuntimeError, which includes a
multi-sentence diagnostic hint): the label has no wrap/scroll, so the whole
Toplevel stretches to fit the text, and plain label text can't be selected or
copied for a bug report.

``show_error_detail`` fixes both: it truncates the status-bar text to a short
summary and opens a separate, fixed-size dialog with the full message in a
selectable/copyable (but read-only) Text widget plus a one-click Copy button.
"""
import tkinter as tk
from tkinter import ttk

_STATUS_SUMMARY_MAX = 100


def show_error_detail(win, status_var, message, title="Error", prefix="Error"):
    """Show a short summary in ``status_var`` and the full ``message`` in a dialog.

    Parameters
    ----------
    win : tk widget
        Parent window for the dialog (and owner of ``status_var``).
    status_var : tk.StringVar or None
        Updated with a short, single-line summary. Pass ``None`` to skip.
    message : str
        The full error text (may be long/multi-sentence).
    title : str
        Dialog window title.
    prefix : str
        Short label prepended to the status-bar summary, e.g. "Error".
    """
    summary = message if len(message) <= _STATUS_SUMMARY_MAX else message[:_STATUS_SUMMARY_MAX] + "\u2026"
    if status_var is not None:
        status_var.set(f"{prefix}: {summary}  (see dialog)")

    dlg = tk.Toplevel(win)
    dlg.title(title)
    dlg.geometry("640x320")
    dlg.transient(win)

    frame = ttk.Frame(dlg, padding=8)
    frame.pack(fill=tk.BOTH, expand=True)

    text = tk.Text(frame, wrap=tk.WORD, height=12)
    scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=text.yview)
    text.configure(yscrollcommand=scrollbar.set)
    text.insert("1.0", message)
    # DISABLED still allows mouse/keyboard selection and Ctrl+C in Tkinter --
    # it only blocks edits, which is exactly the read-only-but-copyable behavior wanted here.
    text.configure(state=tk.DISABLED)
    text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _copy():
        dlg.clipboard_clear()
        dlg.clipboard_append(message)

    btns = ttk.Frame(dlg, padding=(8, 0, 8, 8))
    btns.pack(fill=tk.X)
    ttk.Button(btns, text="Copy to Clipboard", command=_copy).pack(side=tk.LEFT)
    ttk.Button(btns, text="Close", command=dlg.destroy).pack(side=tk.RIGHT)

    dlg.grab_set()
