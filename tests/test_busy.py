"""The one busy signal: cursor, status line, disabled starting button."""
import tkinter as tk
from tkinter import ttk

import pytest

from molass_gui import busy


@pytest.fixture
def root():
    try:
        r = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"no display: {exc}")
    r.withdraw()
    yield r
    r.destroy()


@pytest.fixture
def window(root):
    win = tk.Toplevel(root)
    status = tk.StringVar(master=win, value="Ready")
    button = ttk.Button(win, text="Go")
    button.pack()
    return win, status, button


def cursor(win):
    return str(win.cget("cursor"))


def test_begin_shows_the_cursor_the_status_and_disables_the_button(window):
    win, status, button = window
    token = busy.begin(win, status, "Computing masses\u2026", buttons=[button])
    assert cursor(win) in (busy.BACKGROUND_CURSOR, "watch")
    assert status.get() == "Computing masses\u2026" and button.instate(["disabled"])
    token.end()
    assert cursor(win) == "" and status.get() == "Ready" and not button.instate(["disabled"])


def test_a_blocking_period_shows_the_hourglass(window):
    win, status, button = window
    with busy.working(win, status, "Loading\u2026", buttons=[button]):
        assert cursor(win) in (busy.BLOCKING_CURSOR, "watch") and status.get() == "Loading\u2026"
    assert cursor(win) == "" and not button.instate(["disabled"])


def test_the_state_is_restored_when_the_work_fails(window):
    win, status, button = window
    with pytest.raises(RuntimeError):
        with busy.working(win, status, "Loading\u2026", buttons=[button]):
            raise RuntimeError("boom")
    assert cursor(win) == "" and not button.instate(["disabled"]) and status.get() == "Ready"


def test_a_second_begin_with_the_same_key_is_refused_until_the_first_ends(window):
    win, status, _ = window
    first = busy.begin(win, status, "Computing masses\u2026", key="mass")
    assert busy.begin(win, status, "Computing masses\u2026", key="mass") is None      # the double click
    other = busy.begin(win, status, "Computing continuity\u2026", key="continuity")
    assert other is not None
    first.end()
    assert cursor(win) != ""                                  # the other one is still running
    other.end()
    assert cursor(win) == ""
    assert busy.begin(win, status, "Again\u2026", key="mass") is not None


def test_an_error_message_set_meanwhile_is_not_overwritten(window):
    win, status, _ = window
    token = busy.begin(win, status, "Decomposing\u2026")
    status.set("Error: no peaks")
    token.end()
    assert status.get() == "Error: no peaks"


def test_end_can_set_the_result_text_and_is_idempotent(window):
    win, status, button = window
    token = busy.begin(win, status, "Decomposing\u2026", buttons=[button])
    token.end(status="Used peak positions 40, 84")
    token.end(status="ignored")
    assert status.get() == "Used peak positions 40, 84" and not button.instate(["disabled"])


def test_buttons_that_were_disabled_stay_disabled(window):
    win, status, button = window
    button.state(["disabled"])                  # for another reason, e.g. waiting for the Rg curve
    token = busy.begin(win, status, "Computing\u2026", buttons=[button])
    token.end()
    assert button.instate(["disabled"])


def test_update_changes_the_message_while_busy(window):
    win, status, _ = window
    token = busy.begin(win, status, "Rg: 0/100")
    token.update("Rg: 40/100")
    assert status.get() == "Rg: 40/100"
    token.end(status="")
    assert status.get() == ""
