"""molass-gui#15/#16: NaiveView headless, on fake data (no dataset load, no Rg-curve wait)."""
import time
import tkinter as tk
from types import SimpleNamespace

import numpy as np
import pytest
from matplotlib.figure import Figure

from molass_gui import naive_view
from molass_gui.naive_view import NaiveView


class FakeCorrected:
    def __init__(self, auto_opts, confirmed=(), confirmed_opts=None):
        self.auto_opts = auto_opts
        self.confirmed = list(confirmed)      # the detected positions the XR/UV mapping also sees
        self.confirmed_opts = confirmed_opts
        self.calls = []

    def get_rg_curve(self, progress_cb=None):
        return "rgcurve"

    def recommend_decomposition_options(self, confirm_with_uv=False):
        return self.confirmed_opts if confirm_with_uv and self.confirmed_opts else self.auto_opts

    def get_confirmed_peaks(self):
        positions = [int(p) for p in self.auto_opts.get('xr_peakpositions', [])]
        return SimpleNamespace(positions=positions, confirmed=[p in self.confirmed for p in positions])

    def quick_decomposition(self, **kwargs):
        self.calls.append(kwargs)
        raise RuntimeError("stop here")     # QuickView needs a real decomposition


class FakeTrimmed:
    def __init__(self, corrected):
        self.corrected = corrected

    def corrected_copy(self):
        return self.corrected

    def plot_compact(self, baseline=True):
        fig = Figure()
        ax_xr, ax_uv = fig.subplots(1, 2)
        x = np.arange(200)
        y = np.exp(-0.5*((x - 84)/5.0)**2) + 0.5*np.exp(-0.5*((x - 117)/5.0)**2)
        ax_xr.plot(x, y)
        return SimpleNamespace(fig=fig, axes=[ax_xr, ax_uv], xr_curve=SimpleNamespace(get_xy=lambda: (x, y)))


@pytest.fixture
def root():
    try:
        r = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"no display: {exc}")
    r.withdraw()
    yield r
    r.destroy()


def run_loop(root, condition, first=None, timeout=10):
    """Run the Tk main loop until ``condition()``: the workers hand their results over with ``after``, which
    needs the loop to be running (as in the app); ``first`` is called inside it."""
    end = time.time() + timeout

    def tick():
        if condition() or time.time() > end:
            root.quit()
        else:
            root.after(10, tick)

    if first is not None:
        root.after(0, first)
    root.after(10, tick)
    root.mainloop()
    assert condition(), "timed out"


def open_view(root, corrected):
    """The Naive View, shown and with the detection finished."""
    view = NaiveView(SimpleNamespace(), FakeTrimmed(corrected), SimpleNamespace(), parent=root,
                     app_root=SimpleNamespace(close_session=lambda: None))
    run_loop(root, lambda: enabled(view._decomp_btn), first=view.show)
    return view


def enabled(widget):
    return not widget.instate(["disabled"])


AUTO = {"num_components": 2, "xr_peakpositions": np.array([84, 117])}


def test_detection_fills_in_the_view(root):
    view = open_view(root, FakeCorrected(AUTO, confirmed=[84]))
    assert view._nc_var.get() == 2
    assert view._candidates == [(84, True), (117, False)]
    assert enabled(view._peak_btn)
    assert view._peaks_var.get() == ""      # the library left no peak out: the plain default


# five detected peaks, three of them also seen in UV (the situation of PROTEINS5: 5 of 7)
SEVEN = {"num_components": 5, "xr_peakpositions": np.array([10, 40, 84, 117, 190])}
THREE = {"num_components": 3, "xr_peakpositions": np.array([40, 84, 117])}


def test_confirmed_peaks_are_the_default_when_the_mapping_rules_the_others_out(root):
    corrected = FakeCorrected(SEVEN, confirmed=[40, 84, 117], confirmed_opts=THREE)
    view = open_view(root, corrected)
    assert view._peaks_var.get() == "40, 84, 117" and view._nc_var.get() == 3
    assert "3 of 5 detected peaks" in view._status_var.get()
    view._decompose()
    run_loop(root, lambda: corrected.calls and "stop here" in view._status_var.get())
    assert corrected.calls == [{"num_components": 3, "xr_peakpositions": [40, 84, 117]}]


def test_the_default_peaks_give_way_to_components_and_to_clear(root):
    view = open_view(root, FakeCorrected(SEVEN, confirmed=[40, 84, 117], confirmed_opts=THREE))
    view._nc_var.set(4)                      # the user wants something else: the default positions must not override it
    assert view._peaks_var.get() == "" and view._auto_positions is None
    view._nc_var.set(3)
    view._peaks_var.set("40, 84, 117")
    view._clear_peak_selection()
    assert view._peaks_var.get() == "" and view._nc_var.get() == 5     # back to the plain default


def test_a_failure_after_the_detection_is_shown_and_leaves_the_manual_default(root, monkeypatch):
    def boom(*_args):
        raise ValueError("boom")
    monkeypatch.setattr(naive_view, "classify_peaks", boom)
    view = open_view(root, FakeCorrected(AUTO))
    assert "Auto-detect failed (boom)" in view._status_var.get()
    assert view._nc_var.get() == 3 and enabled(view._nc_spinbox)


def test_decompose_passes_the_typed_peak_positions_to_the_library(root):
    corrected = FakeCorrected(AUTO)
    view = open_view(root, corrected)
    view._peaks_var.set("84, 117")
    run_loop(root, lambda: "stop here" in view._status_var.get(), first=view._decompose)
    assert corrected.calls == [{"num_components": 2, "xr_peakpositions": [84, 117]}]
    assert enabled(view._decomp_btn)       # the failure is reported and Decompose is usable again
    view._proportions_var.set("1, 1")
    view._decompose()
    assert "not both" in view._status_var.get() and len(corrected.calls) == 1
