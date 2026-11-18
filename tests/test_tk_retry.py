"""The Tk start-up retry of conftest.py (molass-gui#24): only the intermittent ``tcl_findLibrary`` failure is retried."""
import tkinter as tk

import pytest

import conftest


def _failing(times, message):
    state = {"calls": 0}

    def init(self, *args, **kwargs):
        state["calls"] += 1
        if state["calls"] <= times:
            raise tk.TclError(message)
    return init, state


def test_the_intermittent_tcl_findlibrary_failure_is_retried(monkeypatch):
    init, state = _failing(2, 'invalid command name "tcl_findLibrary"')
    monkeypatch.setattr(conftest, "_original_init", init)
    monkeypatch.setattr(conftest.time, "sleep", lambda s: None)
    conftest._retrying_init(object())
    assert state["calls"] == 3


def test_it_retries_the_init_tcl_flavour_too(monkeypatch):
    init, state = _failing(1, "Can't find a usable init.tcl\n\nThis probably means that Tcl wasn't installed properly.")
    monkeypatch.setattr(conftest, "_original_init", init)
    monkeypatch.setattr(conftest.time, "sleep", lambda s: None)
    conftest._retrying_init(object())
    assert state["calls"] == 2


def test_it_retries_the_tk_tcl_flavour_too(monkeypatch):
    init, state = _failing(1, "Can't find a usable tk.tcl\ncouldn't read file ttk/fonts.tcl: no such file")
    monkeypatch.setattr(conftest, "_original_init", init)
    monkeypatch.setattr(conftest.time, "sleep", lambda s: None)
    conftest._retrying_init(object())
    assert state["calls"] == 2


def test_it_gives_up_after_the_retries(monkeypatch):
    init, state = _failing(99, 'invalid command name "tcl_findLibrary"')
    monkeypatch.setattr(conftest, "_original_init", init)
    monkeypatch.setattr(conftest.time, "sleep", lambda s: None)
    with pytest.raises(tk.TclError):
        conftest._retrying_init(object())
    assert state["calls"] == conftest._RETRIES


def test_any_other_error_is_raised_at_once(monkeypatch):
    init, state = _failing(1, "no display name and no $DISPLAY environment variable")
    monkeypatch.setattr(conftest, "_original_init", init)
    with pytest.raises(tk.TclError):
        conftest._retrying_init(object())
    assert state["calls"] == 1
