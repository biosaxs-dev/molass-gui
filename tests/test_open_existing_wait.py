"""Open Existing Analysis: the dialog stays on screen, saying what is going on, until the result window is drawn
(the load blocks the main thread for minutes, so a window shown earlier would stay blank and the dialog was gone)."""
import os
import time
import tkinter as tk
from types import SimpleNamespace

import pytest

APP = SimpleNamespace(close_session=lambda: None)


def _pump(root, seconds=0.2):
    end = time.time() + seconds
    while time.time() < end:
        root.update()
        time.sleep(0.01)


@pytest.fixture
def analysis_folder(tmp_path):
    (tmp_path / "optimized").mkdir()
    (tmp_path / "optimized" / "recipe.json").write_text("{}")
    return str(tmp_path)


class FakeView:
    """Stands for RigorousView: records the callbacks, owns a hidden window."""
    last = None

    def __init__(self, parent, on_progress, on_done):
        self.parent, self.on_progress, self.on_done = parent, on_progress, on_done
        self._win = None
        FakeView.last = self

    @classmethod
    def open_existing(cls, folder, parent=None, app_root=None, session_tag=None, on_progress=None, on_done=None):
        return cls(parent, on_progress, on_done)

    def show(self):
        self._win = tk.Toplevel(self.parent)
        self._win.withdraw()


def _open_dialog(root, monkeypatch, folder):
    from molass_gui import recent_folders, rigorous_view, view_analysis
    monkeypatch.setattr(recent_folders, "load", lambda kind="data": [])
    monkeypatch.setattr(recent_folders, "add", lambda *a, **k: None)
    monkeypatch.setattr(rigorous_view.RigorousView, "open_existing", FakeView.open_existing)
    dialog = view_analysis.ViewAnalysisView(parent=root, app_root=SimpleNamespace(close_session=lambda: None))
    dialog.show()
    dialog._folder_var.set(folder)
    _pump(root)
    dialog._run()
    return dialog


def test_the_dialog_stays_until_the_result_is_drawn(root, monkeypatch, analysis_folder):
    dialog = _open_dialog(root, monkeypatch, analysis_folder)
    view = FakeView.last
    view.on_progress("Rebuilding the analysis")
    _pump(root)
    assert dialog._win.winfo_viewable()
    assert dialog._status_var.get() == "Rebuilding the analysis"
    assert dialog._btn.instate(["disabled"])
    assert not view._win.winfo_viewable()

    view.on_done(None)
    _pump(root)
    assert view._win.winfo_viewable()
    assert not dialog._win.winfo_viewable()
    view._win.destroy()


def test_a_failed_load_comes_back_to_the_dialog(root, monkeypatch, analysis_folder):
    dialog = _open_dialog(root, monkeypatch, analysis_folder)
    view = FakeView.last
    view.on_done("recipe is broken")
    _pump(root)
    assert dialog._win.winfo_viewable()
    assert "recipe is broken" in dialog._status_var.get()
    assert not dialog._btn.instate(["disabled"])
    assert not view._win.winfo_exists()
    dialog._win.destroy()


def test_a_second_click_while_loading_does_nothing(root, monkeypatch, analysis_folder):
    dialog = _open_dialog(root, monkeypatch, analysis_folder)
    first = FakeView.last
    dialog._run()
    assert FakeView.last is first
    first.on_done("stop")
    dialog._win.destroy()


def test_rigorous_view_stays_hidden_and_reports_back(root, monkeypatch, tmp_path):
    from molass_gui.rigorous_view import RigorousView
    calls = []
    view = RigorousView.open_existing(str(tmp_path), parent=root, app_root=APP, on_progress=calls.append,
                                      on_done=lambda error: calls.append(("done", error)))
    monkeypatch.setattr(view, "_prep_main_result", lambda: view._load_finished("boom"))
    view.show()
    _pump(root)
    assert not view._win.winfo_viewable()
    assert calls == [("done", "boom")]
    view._load_finished(None)       # reported once only
    assert calls == [("done", "boom")]
    view._win.destroy()


def test_rigorous_view_without_callbacks_is_shown_as_before(root, monkeypatch, tmp_path):
    from molass_gui.rigorous_view import RigorousView
    view = RigorousView.open_existing(str(tmp_path), parent=root, app_root=APP)
    monkeypatch.setattr(view, "_prep_main_result", lambda: None)
    view.show()
    root.update()
    assert view._win.state() == "normal"
    view._win.destroy()


def test_the_stages_of_the_rebuild_are_shown_when_molass_reports_them(tmp_path):
    from molass_gui.rigorous_view import RigorousView
    messages = []
    view = RigorousView.open_existing(str(tmp_path), on_progress=messages.append)

    def rebuild_with_stages(folder, in_folder=None, debug=False, progress_cb=None):
        progress_cb("Trimming", 0.25)
        progress_cb("Done", 1.0)
        return "result"

    def rebuild_without(folder):
        return "result"

    assert view._rebuild_from_recipe(rebuild_with_stages) == "result"
    assert messages == ["Trimming\u2026 (25 %)"]                       # "Done" is not a stage to show
    assert view._rebuild_from_recipe(rebuild_without) == "result"     # an older molass: just the call

