"""A forked view and the view it came from close independently: the close button of either closes that window alone,
the run of the fork is not touched by closing the original, and the fork asks before it is closed itself."""
import time
import tkinter as tk
from types import SimpleNamespace

import pytest

from molass_gui import rigorous_view, window_tree
from molass_gui.rigorous_view import RigorousView

STUB_DECOMP = SimpleNamespace(ssd=SimpleNamespace(xr=SimpleNamespace(jv=[0])))


@pytest.fixture
def app():
    return SimpleNamespace(session_closed=0, close_session=None)


@pytest.fixture(autouse=True)
def no_prep(monkeypatch):
    monkeypatch.setattr(RigorousView, "_prep_main", lambda self: None)
    monkeypatch.setattr(RigorousView, "_prep_main_result", lambda self: None)


def _pump(root, seconds=0.15):
    end = time.time() + seconds
    while time.time() < end:
        root.update()
        time.sleep(0.01)


def _view(root, app, tmp_path, name, parent=None, independent=True):
    view = RigorousView(STUB_DECOMP, None, {}, str(tmp_path / name), ctx=None, parent=parent or root,
                        app_root=app, session_tag=name)
    if independent:
        view._make_independent()
    view.show()
    return view


def _running(view):
    stopped = []
    view._run_info = SimpleNamespace(is_alive=True, stop=lambda: stopped.append(True))
    return stopped


def _ask(monkeypatch, answer):
    asked = []

    def askyesno(title, message, **kw):
        asked.append(message)
        return answer
    monkeypatch.setattr(window_tree.messagebox, "askyesno", askyesno)
    return asked


def test_closing_the_original_leaves_the_running_fork_alone(root, app, tmp_path, monkeypatch):
    asked = _ask(monkeypatch, False)
    original = _view(root, app, tmp_path, "original")
    fork = _view(root, app, tmp_path, "fork")
    stopped = _running(fork)
    original._close_own()
    _pump(root)
    assert asked == []                                   # nothing to ask: the fork is not part of it
    assert not original._win.winfo_exists()
    assert fork._win.winfo_exists() and stopped == []
    fork._win.destroy()


def test_closing_the_fork_asks_and_stops_only_its_own_run(root, app, tmp_path, monkeypatch):
    original = _view(root, app, tmp_path, "original")
    fork = _view(root, app, tmp_path, "fork")
    stopped = _running(fork)
    original_stopped = _running(original)
    original._run_info.is_alive = False

    asked = _ask(monkeypatch, False)
    fork._close_own()
    assert len(asked) == 1 and "Rigorous optimization run in progress" in asked[0]
    assert fork._win.winfo_exists() and stopped == []      # "No": nothing happens

    asked = _ask(monkeypatch, True)
    fork._close_own()
    _pump(root)
    assert not fork._win.winfo_exists() and stopped == [True]
    assert original._win.winfo_exists() and original_stopped == []
    original._win.destroy()


def test_pending_callbacks_of_a_closed_window_do_not_run(root, app, tmp_path, monkeypatch):
    _ask(monkeypatch, True)
    view = _view(root, app, tmp_path, "view")
    calls = []
    view._after(50, lambda: calls.append(1))
    view._close_own()
    _pump(root, 0.3)
    assert calls == [] and not view._after_ids
    view._after(0, lambda: calls.append(2))              # e.g. from a worker thread that ends later
    _pump(root)
    assert calls == []


def test_a_fork_hangs_from_the_root_and_both_close_alone(root, app, tmp_path, monkeypatch):
    original = _view(root, app, tmp_path, "original", independent=False)
    assert not original._independent
    made = []
    monkeypatch.setattr(RigorousView, "show", lambda self: made.append(self))
    monkeypatch.setattr(rigorous_view.fork_logic, "optimize_extras", lambda plan: {})
    plan = SimpleNamespace(recipe={"method": "bh"}, new_folder=str(tmp_path / "fork"), decomposition=None,
                           info=SimpleNamespace(trimmed=None))
    original._status_var.set("")
    original._start_fork(plan, None, 1, "BH")
    fork, = made
    assert fork._parent is root                          # not a child of the original
    assert fork._independent and original._independent    # the original closes alone from now on
    original._win.destroy()


def test_the_withdrawn_open_existing_dialog_goes_with_its_last_result_window(root, app, tmp_path, monkeypatch):
    _ask(monkeypatch, True)
    dialog = tk.Toplevel(root)
    dialog.withdraw()
    view = _view(root, app, tmp_path, "result", parent=dialog)
    view._close_own()
    assert not dialog.winfo_exists()

    visible = tk.Toplevel(root)                          # a visible parent (a pipeline window) stays
    view = _view(root, app, tmp_path, "result2", parent=visible)
    view._close_own()
    assert visible.winfo_exists()
    visible.destroy()
