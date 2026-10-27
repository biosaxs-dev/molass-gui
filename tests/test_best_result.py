"""The dialogs share one way to get the best rigorous result (molass-library#336)."""
import pytest

import molass.Rigorous.CurrentStateUtils as csu
from molass_gui import best_result


@pytest.fixture
def shown(monkeypatch):
    messages = []
    monkeypatch.setattr(best_result.messagebox, "showinfo", lambda title, text, parent=None: messages.append(title))
    return messages


def test_returns_the_library_result(monkeypatch, shown):
    calls = []

    def fake(decomp, analysis_folder, rgcurve=None, xr_ranks=None, debug=False):
        calls.append((decomp, analysis_folder, rgcurve, xr_ranks))
        return "result"

    monkeypatch.setattr(csu, "load_best_rigorous_result", fake)
    assert best_result.load_best_result("win", "decomp", "folder", rgcurve="rg", xr_ranks=[1]) == "result"
    assert calls == [("decomp", "folder", "rg", [1])] and shown == []


def test_no_result_yet_shows_the_message_and_returns_none(monkeypatch, shown):
    def fake(*args, **kwargs):
        raise csu.NoCompletedJobError("none yet")

    monkeypatch.setattr(csu, "load_best_rigorous_result", fake)
    assert best_result.load_best_result("win", "decomp", "folder") is None
    assert shown == ["No results yet"]


def test_other_errors_are_not_swallowed(monkeypatch, shown):
    def fake(*args, **kwargs):
        raise FileNotFoundError("some other file")

    monkeypatch.setattr(csu, "load_best_rigorous_result", fake)
    with pytest.raises(FileNotFoundError, match="some other file"):
        best_result.load_best_result("win", "decomp", "folder")
    assert shown == []


def test_fallback_for_a_molass_without_the_function(monkeypatch, shown):
    from collections import namedtuple
    Job = namedtuple("Job", "id best_fv")
    loaded = []
    monkeypatch.setattr(csu, "list_rigorous_jobs", lambda folder: [Job("000", 0.5), Job("001", 0.2), Job("002", 0.4)])
    monkeypatch.setattr(csu, "load_rigorous_result",
                        lambda decomp, folder, jobid=None, rgcurve=None, xr_ranks=None:
                        loaded.append(jobid) or type("R", (), {})())
    result = best_result._load_best_fallback("decomp", "folder")
    assert loaded == ["001"] and result.fv == 0.2 and result.sv == pytest.approx(csu.fv_to_sv(0.2))
    monkeypatch.setattr(csu, "list_rigorous_jobs", lambda folder: [])
    with pytest.raises(FileNotFoundError):
        best_result._load_best_fallback("decomp", "folder")
