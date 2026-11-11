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


def test_editing_the_default_peaks_keeps_the_edit(root):
    """Adding or removing a peak (by typing or by a click) in the pre-filled field must not clear it: Components
    follows the new count, and Decompose uses exactly these peaks, not the greedy default."""
    corrected = FakeCorrected(SEVEN, confirmed=[40, 84, 117], confirmed_opts=THREE)
    view = open_view(root, corrected)
    for text in ("10, 40, 84, 117", "40, 84", "40, 84, 117, 190", "40, 84, 117, 1"):   # the last: typing in progress
        view._peaks_var.set(text)
        assert view._peaks_var.get() == text and view._auto_positions is None
    view._peaks_var.set("10, 40, 84, 117, 190")
    assert view._nc_var.get() == 5
    run_loop(root, lambda: corrected.calls and "stop here" in view._status_var.get(), first=view._decompose)
    assert corrected.calls == [{"num_components": 5, "xr_peakpositions": [10, 40, 84, 117, 190]}]


def test_a_click_on_the_curve_adds_a_peak_to_the_default_ones(root):
    from molass_gui.peak_selection import toggle_peak
    view = open_view(root, FakeCorrected(SEVEN, confirmed=[40, 84, 117], confirmed_opts=THREE))
    new = toggle_peak(view._current_positions(), 190, view._xr_x, view._xr_y, candidates=[f for f, _ in view._candidates])
    view._peaks_var.set(", ".join(str(p) for p in new))          # what _on_curve_click does
    assert view._peaks_var.get() == "40, 84, 117, 190" and view._nc_var.get() == 4


def test_typed_proportions_replace_the_default_peaks(root):
    corrected = FakeCorrected(SEVEN, confirmed=[40, 84, 117], confirmed_opts=THREE)
    view = open_view(root, corrected)
    assert view._peaks_var.get() == "40, 84, 117"
    view._proportions_var.set("1, 2")
    assert view._peaks_var.get() == "" and view._nc_var.get() == 2
    run_loop(root, lambda: corrected.calls and "stop here" in view._status_var.get(), first=view._decompose)
    assert corrected.calls == [{"num_components": 2, "proportions": [1.0, 2.0]}]


def _busy_cursor(widget):
    return str(widget.cget("cursor")) != ""


def test_detection_and_decompose_show_the_one_busy_signal(root):
    corrected = FakeCorrected(AUTO)
    view = NaiveView(SimpleNamespace(), FakeTrimmed(corrected), SimpleNamespace(), parent=root,
                     app_root=SimpleNamespace(close_session=lambda: None))
    seen = {}

    def show_and_look():
        view.show()
        seen["detect"] = (view._status_var.get(), _busy_cursor(view._win), view._decomp_btn.instate(["disabled"]))

    run_loop(root, lambda: enabled(view._decomp_btn), first=show_and_look)
    assert seen["detect"] == ("Detecting components\u2026", True, True)
    assert not _busy_cursor(view._win)                                # over: the cursor is back

    def decompose_and_look():
        view._decompose()
        seen["decompose"] = (view._status_var.get(), _busy_cursor(view._win), view._decomp_btn.instate(["disabled"]))

    run_loop(root, lambda: "stop here" in view._status_var.get(), first=decompose_and_look)
    assert seen["decompose"] == ("Decomposing\u2026", True, True)
    assert not _busy_cursor(view._win) and enabled(view._decomp_btn)    # the failure ended the busy state too


def test_a_failed_detection_ends_the_busy_state(root, monkeypatch):
    def boom(*_args):
        raise ValueError("boom")
    monkeypatch.setattr(naive_view, "classify_peaks", boom)
    view = open_view(root, FakeCorrected(AUTO))
    assert not _busy_cursor(view._win)


def test_a_shortfall_and_the_library_warning_reach_the_next_view(root, monkeypatch):
    """Asked for 5, the library warns and returns 3: QuickView gets the notices (molass-gui#19)."""
    import warnings
    import molass_gui.quick_view as quick_view

    class ShortCorrected(FakeCorrected):
        def quick_decomposition(self, **kwargs):
            self.calls.append(kwargs)
            warnings.warn(f"quick_decomposition(num_components={kwargs['num_components']}) returned 3 components: "
                          "peak recognition found only 3 peaks. To get 5 components, pass proportions=[1]*5.", UserWarning)
            return SimpleNamespace(get_num_components=lambda: 3)

    received = {}

    class RecordingQuickView:
        def __init__(self, *args, found_notices=(), **kwargs):
            received["notices"] = list(found_notices)

        def show(self):
            pass

    monkeypatch.setattr(quick_view, "QuickView", RecordingQuickView)
    corrected = ShortCorrected(AUTO)
    view = open_view(root, corrected)
    view._nc_var.set(5)
    view._win.withdraw = lambda: None
    run_loop(root, lambda: "notices" in received, first=view._decompose)
    assert received["notices"][0] == "Asked for 5 components, got 3."
    assert received["notices"][1].startswith("To get 5 components")


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
