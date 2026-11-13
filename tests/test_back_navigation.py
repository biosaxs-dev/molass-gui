"""molass-gui#20: the "Naive View" button of the Quick View and the "Quick View" button of the Upgraded View, headless on
fake decompositions."""
import queue
import time
import tkinter as tk
from types import SimpleNamespace

import pytest
from matplotlib.figure import Figure

from molass_gui import quick_view, upgraded_view
from molass_gui.rgcurve_worker import attach_rgcurve_worker
from molass_gui.session_context import SessionContext


class FakeDecomp:
    def __init__(self):
        self.ssd = SimpleNamespace(xr=SimpleNamespace(jv=range(10)))

    def plot_components(self, **kwargs):
        return SimpleNamespace(fig=Figure())

    def get_num_components(self):
        return 2


@pytest.fixture
def root():
    try:
        r = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"no display: {exc}")
    r.withdraw()
    yield r
    r.destroy()


def pump(root, seconds=0.3):
    end = time.time() + seconds
    while time.time() < end:
        root.update()
        time.sleep(0.01)


def enabled(widget):
    return not widget.instate(["disabled"])


APP_ROOT = SimpleNamespace(close_session=lambda: None)


def test_forget_decomposition_resets_what_the_decomposition_and_later_views_set():
    ctx = SessionContext("folder")
    ctx.num_components, ctx.proportions, ctx.xr_peakpositions = 3, [1, 1, 1], [10, 20, 30]
    ctx.proportions_source, ctx.trust_proportions, ctx.constraint_weight = "uv", False, 0.5
    ctx.model_info, ctx.xr_ranks = {"model": "edm"}, [1, 1, 2]
    ctx.uv_pickat = 290
    ctx.forget_decomposition()
    fresh = SessionContext("folder")
    assert {k: v for k, v in vars(ctx).items() if k != "uv_pickat"} == {k: v for k, v in vars(fresh).items() if k != "uv_pickat"}
    assert ctx.uv_pickat == 290      # what belongs to loading stays


def test_quick_view_back_closes_the_view_and_hands_back_the_rg_curve(root):
    backs = []
    view = quick_view.QuickView(FakeDecomp(), None, 2, SessionContext("folder"), parent=root, app_root=APP_ROOT,
                                rgcurve="rg", back=backs.append)
    view.show()
    win = view._win
    assert enabled(view._action_btn) and enabled(view._back_btn)      # the curve is there: nothing to wait for
    view._back_btn.invoke()
    assert backs == ["rg"] and not win.winfo_exists()


def test_quick_view_back_while_the_rg_curve_is_computed_leaves_the_queue_to_the_next_view(root):
    q = queue.Queue()
    view = quick_view.QuickView(FakeDecomp(), None, 2, SessionContext("folder"), parent=root, app_root=APP_ROOT,
                                rgcurve_queue=q, back=lambda rgcurve: None)
    view.show()
    view._back_btn.invoke()
    q.put(("done", "rg"))
    pump(root, 0.5)
    assert q.get_nowait() == ("done", "rg")        # the closed view's polling did not take it


def test_attach_polling_still_delivers_in_an_open_view(root):
    win = tk.Toplevel(root)
    q, got = queue.Queue(), []
    attach_rgcurve_worker(win, q, 10, None, got.append)
    q.put(("done", "rg"))
    pump(root, 0.5)
    assert got == ["rg"]


def test_upgraded_view_back_shows_the_quick_view_again_and_the_run_blocks_it(root, monkeypatch):
    monkeypatch.setattr(upgraded_view, "fmt_fronting", lambda *a, **k: "")
    backs = []
    model_info = {"model": "edm", "pore_dist": None, "ln_pore_sigma": None}
    view = upgraded_view.UpgradedView(FakeDecomp(), None, 2, model_info, SessionContext("folder"), parent=root,
                                      app_root=APP_ROOT, rgcurve="rg", back=lambda: backs.append("back"))
    view.show()
    win = view._win
    view._back_btn.invoke()
    assert backs == ["back"] and not win.winfo_exists()


def test_quick_view_shows_again_with_the_upgrade_undone(root):
    ctx = SessionContext("folder")
    view = quick_view.QuickView(FakeDecomp(), None, 2, ctx, parent=root, app_root=APP_ROOT, rgcurve="rg",
                                back=lambda rgcurve: None)
    view.show()
    ctx.model_info = {"model": "edm"}
    view._win.withdraw()
    view._show_again()
    assert ctx.model_info is None and view._win.state() == "normal"


def test_naive_view_comes_back_ready_to_decompose_again_with_the_rg_curve(root, monkeypatch):
    from test_naive_view_smoke import AUTO, FakeCorrected, open_view, run_loop

    received = []

    class RecordingQuickView:
        def __init__(self, *args, **kwargs):
            received.append(kwargs)

        def show(self):
            pass

    monkeypatch.setattr(quick_view, "QuickView", RecordingQuickView)

    class Corrected(FakeCorrected):
        def quick_decomposition(self, **kwargs):
            self.calls.append(kwargs)
            return SimpleNamespace(get_num_components=lambda: kwargs["num_components"])

    view = open_view(root, Corrected(AUTO))
    view._ctx = SessionContext("folder")
    view._ctx.model_info = {"model": "edm"}
    view._peaks_var.set("84, 117")
    view._win.withdraw = lambda: None
    run_loop(root, lambda: len(received) == 1, first=view._decompose)
    assert received[0]["rgcurve"] is None

    view._show_again("rg")
    assert view._ctx.model_info is None and view._peaks_var.get() == "84, 117"      # the entries stay
    run_loop(root, lambda: len(received) == 2 and enabled(view._decomp_btn), first=view._decompose)
    assert received[1]["rgcurve"] == "rg"
