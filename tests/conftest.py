"""Shared test setup.

Creating a Tk interpreter sometimes fails on Windows / Python 3.14 with ``invalid command name "tcl_findLibrary"``,
about one run of the suite in several and in a different test each time (molass-gui#24). It happens in the roots of
the tests and also in matplotlib's own ``tk.Tk(className="matplotlib")`` inside ``plt.figure()``, so the retry sits
in ``tkinter.Tk.__init__``. The failure comes in three flavours (``tcl_findLibrary``, "Can't find a usable
init.tcl", "Can't find a usable tk.tcl ... couldn't read file ... ttk/fonts.tcl" although the file is there), i.e.
a library file that cannot be read at that moment. Any other ``TclError`` (no display, ...) is raised at once.
"""
import time
import tkinter as tk

import pytest

_RETRIES = 4
_START_UP_FAILURES = ("tcl_findLibrary", "init.tcl", "tk.tcl", "wasn't installed properly")
_original_init = tk.Tk.__init__


def _retrying_init(self, *args, **kwargs):
    for attempt in range(_RETRIES):
        try:
            return _original_init(self, *args, **kwargs)
        except tk.TclError as exc:
            if not any(s in str(exc) for s in _START_UP_FAILURES) or attempt == _RETRIES - 1:
                raise
            time.sleep(0.2)


tk.Tk.__init__ = _retrying_init


@pytest.fixture
def root():
    """A withdrawn Tk root, destroyed after the test; the test is skipped if there is no display."""
    try:
        r = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"no display: {exc}")
    r.withdraw()
    yield r
    r.destroy()
