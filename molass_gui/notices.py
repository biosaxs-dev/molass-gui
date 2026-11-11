"""Show what the library says (molass-gui#19): warnings raised by molass during a step, and "asked for N components, got M".

The library warns (``UserWarning``) when a result is not what was asked for or looks implausible (molass-library#321,
#371, #372). Without this module those warnings go to a stderr that nobody reads, and the user only sees a decomposition
that differs from the request. Tk-free logic first, then the small bar that shows the notices (one line and a Details
button; no popup).
"""
import contextlib
import re
import tkinter as tk
import warnings
from tkinter import ttk

from molass_gui.dpi import px

# the library's own "returned n components" warning says the same as our "asked for N, got M" line
_REDUNDANT = re.compile(r"returned \d+ components")


@contextlib.contextmanager
def capture():
    """``with capture() as caught:`` records the ``UserWarning`` messages raised inside (numerical noise such as
    ``RuntimeWarning`` is left alone). The list fills when the block ends. ``warnings.catch_warnings`` changes global
    state, so use it around a single step, not around long-lived code."""
    caught = []
    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        try:
            yield caught
        finally:
            caught.extend(str(w.message).strip() for w in record if issubclass(w.category, UserWarning))


def count_notice(requested, actual):
    """``"Asked for 7 components, got 3."`` when they differ, else None."""
    if requested is None or actual is None or requested == actual:
        return None
    return f"Asked for {requested} components, got {actual}."


def build_notices(requested=None, actual=None, caught=()):
    """The notices of a step, most important first, without duplicates: the count line, then the library's warnings."""
    notices = []
    first = count_notice(requested, actual)
    if first is not None:
        notices.append(first)
    for message in caught:
        if not message or message in notices:
            continue
        if first is not None and _REDUNDANT.search(message):
            # keep the library's advice (how to get more components), the count is already said
            advice = message.split(".", 1)[1].strip() if "." in message else ""
            message = advice or message
            if message in notices:
                continue
        notices.append(message)
    return notices


def summary(notices):
    """One line for the status bar: the first notice and how many more there are."""
    if not notices:
        return ""
    more = len(notices) - 1
    return notices[0] if not more else f"{notices[0]}  (+{more} more)"


def details_text(notices):
    return "\n\n".join(f"{i}. {n}" for i, n in enumerate(notices, start=1))


class NoticeBar:
    """A line with the first notice and a Details button, packed under the header; does nothing without notices."""

    def __init__(self, win, notices):
        self.notices = list(notices)
        self._win = win
        self.frame = None
        if not self.notices:
            return
        self.frame = ttk.Frame(win, padding=(8, 2))
        self.frame.pack(fill=tk.X)
        self.label = ttk.Label(self.frame, text="\u26a0 " + summary(self.notices), foreground="#b45309",
                               wraplength=px(1000), justify=tk.LEFT)
        self.label.pack(side=tk.LEFT)
        ttk.Button(self.frame, text="Details\u2026", command=self.show_details).pack(side=tk.LEFT, padx=8)

    def show_details(self):
        from molass_gui.error_dialog import show_error_detail
        show_error_detail(self._win, None, details_text(self.notices), title="Notices from molass", prefix="Notice")
