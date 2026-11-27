"""Rank-2 report dialog (molass-gui#27): ``repr(decomposition.rank2_report())`` in a read-only monospace text with a Copy button, to paste into a
status record or a mail. The report is the one computed when the ranks were applied; nothing is recomputed here and nothing can be edited
(the report shows what the data support, it is not a tuning panel)."""
import tkinter as tk
from tkinter import ttk

from molass_gui.dpi import geometry


def report_text(report):
    """The text of the report, or ``""`` when there is none."""
    return repr(report) if report else ""


def show_rank2_report(win, text, heading=None):
    """Open the dialog with *text*; returns the Toplevel."""
    dlg = tk.Toplevel(win)
    dlg.title("Rank-2 report")
    dlg.geometry(geometry(900, 520))
    dlg.transient(win)

    if heading:
        ttk.Label(dlg, text=heading).pack(anchor=tk.W, padx=8, pady=(8, 0))
    frame = ttk.Frame(dlg, padding=8)
    frame.pack(fill=tk.BOTH, expand=True)
    box = tk.Text(frame, wrap=tk.WORD, height=16, font="TkFixedFont")
    scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=box.yview)
    box.configure(yscrollcommand=scrollbar.set)
    box.insert("1.0", text)
    box.configure(state=tk.DISABLED)          # still selectable and copyable with Ctrl+C
    box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _copy():
        dlg.clipboard_clear()
        dlg.clipboard_append(text)

    btns = ttk.Frame(dlg, padding=(8, 0, 8, 8))
    btns.pack(fill=tk.X)
    ttk.Button(btns, text="Copy to Clipboard", command=_copy).pack(side=tk.LEFT)
    ttk.Button(btns, text="Close", command=dlg.destroy).pack(side=tk.RIGHT)
    dlg.copy = _copy
    dlg.text_widget = box
    return dlg
