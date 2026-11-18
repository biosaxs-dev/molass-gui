"""The Recent list of the folder pickers is wide enough to read the end of a long path (the paths of the Open
Existing Analysis window were cut off at 52 characters)."""
import time
import tkinter as tk
import tkinter.font as tkfont
from types import SimpleNamespace

import pytest

from molass_gui import recent_folders
from molass_gui.recent_folders import MAX_WIDTH, MIN_WIDTH, picker_width

LONG = [
    "C:/Users/takahashi/MOLASS/analyses-for-papers/Q4/analysis-GRM-from-EGH",
    "C:/Users/takahashi/MOLASS/analyses-for-papers/Q4p5/analysis-EGH-with-a-long-name-2",
    "C:/Users/takahashi/MOLASS/analyses-for-papers/Q3/analysis-004",
]


def test_the_width_follows_the_longest_path_within_limits():
    assert picker_width([]) == MIN_WIDTH
    assert picker_width(["C:/short"]) == MIN_WIDTH
    longest = max(len(p) for p in LONG)
    assert picker_width(LONG) == longest + 6 and longest + 6 > MIN_WIDTH
    assert picker_width(["x" * 500]) == MAX_WIDTH


def _pump(root, seconds=0.2):
    end = time.time() + seconds
    while time.time() < end:
        root.update()
        time.sleep(0.01)


def _combobox(window):
    from tkinter import ttk

    def walk(w):
        for child in w.winfo_children():
            if isinstance(child, ttk.Combobox):
                return child
            found = walk(child)
            if found is not None:
                return found
    return walk(window)


def test_open_existing_shows_the_whole_of_the_longest_recent_path(root, monkeypatch):
    from molass_gui import view_analysis
    monkeypatch.setattr(recent_folders, "load", lambda kind="data": list(LONG))
    view = view_analysis.ViewAnalysisView(parent=root, app_root=SimpleNamespace(close_session=lambda: None))
    view.show()
    _pump(root)
    box = _combobox(view._win)
    font = tkfont.nametofont(str(box.cget("font")) if str(box.cget("font")) else "TkTextFont")
    needed = max(font.measure(p) for p in LONG)
    assert box.winfo_reqwidth() >= needed, (box.winfo_reqwidth(), needed)       # the popup list is as wide as the box
    entry = [w for w in view._win.winfo_children()[0].winfo_children() if w.winfo_class() == "TEntry"][0]
    assert entry.winfo_reqwidth() >= needed                                       # and the folder entry above it
    view._win.destroy()


def test_new_analysis_picker_is_widened_too(root, monkeypatch):
    from molass_gui import app
    monkeypatch.setattr(recent_folders, "load", lambda kind="data": list(LONG))
    window = app.App(parent=root, app_root=SimpleNamespace(close_session=lambda: None))
    window.show()
    _pump(root)
    box = _combobox(window._win)
    needed = max(tkfont.nametofont("TkTextFont").measure(p) for p in LONG)
    recent_boxes = [w for w in _all_widgets(window._win) if w.winfo_class() == "TCombobox"
                    and LONG[0] in w.cget("values")]
    assert recent_boxes and recent_boxes[0].winfo_reqwidth() >= needed
    window._win.destroy()


def _all_widgets(widget):
    for child in widget.winfo_children():
        yield child
        yield from _all_widgets(child)
