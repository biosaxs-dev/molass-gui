"""The Trimming dialog of the Naive View: the figure of the trimming the session used, drawn on the entire data."""
import tkinter as tk
from types import SimpleNamespace

import pytest
from matplotlib import pyplot as plt

from molass_gui import dpi, trimming_dialog
from molass_gui.trimming_dialog import show_trimming


class FakeSsd:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []

    def plot_trimming(self, trim=None, **kwargs):
        self.calls.append(trim)
        if self.fail:
            raise RuntimeError("cannot draw")
        fig = plt.figure(figsize=(16, 8))
        fig.subplots(2, 3)
        return SimpleNamespace(fig=fig)


@pytest.fixture
def root():
    try:
        r = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"no display: {exc}")
    r.withdraw()
    yield r
    r.destroy()
    plt.close("all")


@pytest.fixture
def errors(monkeypatch):
    shown = []
    import molass_gui.error_dialog as error_dialog
    monkeypatch.setattr(error_dialog, "show_error_detail",
                        lambda win, status_var, message, title="Error", prefix="Error": shown.append((title, message)))
    return shown


def test_it_draws_the_trimming_the_session_used_at_the_size_of_a_dialog(root, errors):
    ssd, trimming = FakeSsd(), object()
    dlg = show_trimming(root, tk.StringVar(master=root), ssd, SimpleNamespace(trimming=trimming))
    assert ssd.calls == [trimming]          # not None: a fresh default trimming would ignore the Load dialog's choice
    assert dlg.title() == "Trimming" and not errors
    fig = plt.gcf()
    assert tuple(fig.get_size_inches()) == (16, 8)       # the layout plot_trimming() made is kept, not redone
    assert fig.get_figwidth() * fig.dpi == dpi.px(trimming_dialog.WINDOW_WIDTH)     # shrunk to the window by dpi


def test_an_open_dialog_is_raised_not_drawn_again(root, errors):
    ssd, trimmed, status = FakeSsd(), SimpleNamespace(trimming=object()), tk.StringVar(master=root)
    first = show_trimming(root, status, ssd, trimmed)
    assert show_trimming(root, status, ssd, trimmed, previous=first) is first
    assert len(ssd.calls) == 1
    first.destroy()
    again = show_trimming(root, status, ssd, trimmed, previous=first)      # closed: a new one
    assert again is not first and len(ssd.calls) == 2


def test_closing_the_session_closes_the_figure(root, errors):
    from molass_gui.window_tree import close_window
    dlg = show_trimming(root, tk.StringVar(master=root), FakeSsd(), SimpleNamespace(trimming=object()))
    assert plt.get_fignums()
    close_window(dlg)
    assert not plt.get_fignums()


def test_data_without_trimming_information_is_reported(root, errors):
    ssd = FakeSsd()
    assert show_trimming(root, tk.StringVar(master=root), ssd, SimpleNamespace(trimming=None)) is None
    assert errors[0][0] == "Trimming unavailable" and ssd.calls == []


def test_a_failing_plot_is_reported_and_ends_the_busy_state(root, errors):
    status = tk.StringVar(master=root)
    assert show_trimming(root, status, FakeSsd(fail=True), SimpleNamespace(trimming=object())) is None
    assert errors == [("Trimming plot failed", "cannot draw")]
    assert status.get() == ""
