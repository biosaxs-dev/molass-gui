"""The Mapping dialog of the Naive View: the UV/XR frame mapping the session's trimming rests on."""
import tkinter as tk
from types import SimpleNamespace

import numpy as np
import pytest
from matplotlib import pyplot as plt

from molass_gui import mapping_dialog
from molass_gui.mapping_dialog import mapping_texts, pair_points, kept_xr_frames, make_figure, show_mapping


class FakeMoment:
    def __init__(self, mean, std):
        self.mean, self.std = mean, std

    def get_meanstd(self):
        return self.mean, self.std


class FakeMapping:
    """A mapping UV = 1.5 XR - 2 of two matched peaks (shape of molass.Mapping.MappingInfo)."""
    slope, intercept = 1.5, -2.0
    resolution_frames = 0.05
    xr_peaks, uv_peaks = [30, 70], [43, 103]
    xr_moment = uv_moment = None
    quality = SimpleNamespace(correlation=0.92, coverage=1.0)

    def __init__(self, plausible=True):
        self.plausible = plausible
        self.xr_curve = SimpleNamespace(x=np.arange(100.0), y=np.exp(-0.5*((np.arange(100) - 30)/4.0)**2))
        self.uv_curve = SimpleNamespace(x=np.arange(150.0), y=np.exp(-0.5*((np.arange(150) - 43)/6.0)**2))
        self.xr_peak_frames = self.xr_curve.x[self.xr_peaks]
        self.uv_peak_frames = self.uv_curve.x[self.uv_peaks]

    def is_plausible(self):
        return self.plausible

    def xr_to_uv(self, x):
        return self.slope*np.asarray(x) + self.intercept

    def uv_to_xr(self, x):
        return (np.asarray(x) - self.intercept)/self.slope


class SinglePeakMapping(FakeMapping):
    xr_peaks, uv_peaks = [30], [43]
    resolution_frames = None
    xr_moment, uv_moment = FakeMoment(30.0, 4.0), FakeMoment(43.0, 6.0)


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


def test_the_texts_give_the_equation_the_numbers_and_the_verdict():
    equation, numbers, verdict, plausible = mapping_texts(FakeMapping())
    assert equation == "UV frame = 1.5 \u00d7 XR frame - 2"
    assert "shape correlation 0.92" in numbers and "coverage 1.00" in numbers and "2 matched peaks" in numbers
    assert "0.05 XR frame" in numbers
    assert verdict == "plausible" and plausible


def test_an_implausible_mapping_says_so():
    _, _, verdict, plausible = mapping_texts(FakeMapping(plausible=False))
    assert verdict.startswith("implausible") and not plausible


def test_a_single_peak_mapping_is_marked_as_less_certain():
    _, numbers, _, _ = mapping_texts(SinglePeakMapping())
    assert "one peak" in numbers and "uncertainty" not in numbers


def test_the_pair_points_are_the_peaks_or_for_one_peak_the_mean_and_width():
    xr, uv = pair_points(FakeMapping())
    assert list(xr) == [30, 70] and list(uv) == [43, 103]
    xr, uv = pair_points(SinglePeakMapping())
    assert list(xr) == [26, 30, 34] and list(uv) == [37, 43, 49]


def test_the_kept_frames_come_from_the_trimming_slice_and_fail_soft():
    trimming = SimpleNamespace(xr_slices=(None, slice(10, 60)), mapping=FakeMapping())
    assert kept_xr_frames(trimming) == (10.0, 59.0)
    assert kept_xr_frames(SimpleNamespace(xr_slices=(None, None), mapping=FakeMapping())) is None
    assert kept_xr_frames(object()) is None


def test_the_figure_has_the_overlay_and_the_peak_pairs():
    fig = make_figure(FakeMapping(), SimpleNamespace(xr_slices=(None, slice(10, 60)), mapping=FakeMapping()))
    overlay, pairs = fig.axes[0], fig.axes[1]       # axes[2] is the twin (UV) axis of the overlay
    assert "Overlay" in overlay.get_title() and "pairs" in pairs.get_title()
    assert len(pairs.lines) == 2 and list(pairs.lines[1].get_xdata()) == [30, 70]    # the fitted line, the peaks


def test_the_dialog_opens_and_closing_the_session_closes_it(root, errors):
    from molass_gui.window_tree import close_window
    dlg = show_mapping(root, tk.StringVar(master=root), SimpleNamespace(trimming=SimpleNamespace(
        mapping=FakeMapping(), xr_slices=(None, None))))
    assert dlg.title() == "Mapping" and not errors
    close_window(dlg)
    assert not dlg.winfo_exists()


def test_an_open_dialog_is_raised_not_built_again(root, errors):
    trimmed = SimpleNamespace(trimming=SimpleNamespace(mapping=FakeMapping(), xr_slices=(None, None)))
    status = tk.StringVar(master=root)
    first = show_mapping(root, status, trimmed)
    assert show_mapping(root, status, trimmed, previous=first) is first


def test_data_without_a_mapping_is_reported(root, errors):
    assert show_mapping(root, tk.StringVar(master=root), SimpleNamespace(trimming=SimpleNamespace(mapping=None))) is None
    assert errors[0][0] == "Mapping unavailable"
