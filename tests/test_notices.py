"""molass-gui#19: the library's warnings and "asked for N components, got M" are shown, not lost."""
import tkinter as tk
import warnings
from types import SimpleNamespace

import pytest

from molass_gui import notices
from molass_gui.notices import build_notices, summary, count_notice, details_text

LIBRARY_WARNING = ("quick_decomposition(num_components=7) returned 3 components: peak recognition found only 3 peaks. "
                   "To get 7 components, pass proportions=[1]*7 (proportional slicing) or xr_peakpositions=[...] "
                   "with 7 frame positions.")


def test_count_notice_only_when_the_counts_differ():
    assert count_notice(7, 3) == "Asked for 7 components, got 3."
    assert count_notice(5, 5) is None and count_notice(None, 3) is None


def test_the_library_warning_is_kept_for_its_advice_but_not_repeated():
    found = build_notices(7, 3, [LIBRARY_WARNING])
    assert found[0] == "Asked for 7 components, got 3."
    assert len(found) == 2 and found[1].startswith("To get 7 components, pass proportions=[1]*7")
    assert "returned 3 components" not in details_text(found)


def test_other_warnings_follow_and_duplicates_go():
    implausible = "component(s) 2 (Rg=7.9) look physically implausible; the data Rg is 27-30"
    found = build_notices(3, 3, [implausible, implausible, ""])
    assert found == [implausible]
    assert summary(found) == implausible
    assert summary(build_notices(7, 3, [LIBRARY_WARNING, implausible])).endswith("(+2 more)")
    assert summary([]) == "" and build_notices(5, 5, []) == []


def test_capture_records_user_warnings_only():
    with notices.capture() as caught:
        warnings.warn("a user warning", UserWarning)
        warnings.warn("numerical noise", RuntimeWarning)
    assert caught == ["a user warning"]


def test_capture_still_fills_the_list_when_the_block_raises():
    caught = []
    with pytest.raises(ValueError):
        with notices.capture() as caught:
            warnings.warn("before the failure", UserWarning)
            raise ValueError("boom")
    assert caught == ["before the failure"]


@pytest.fixture
def root():
    try:
        r = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"no display: {exc}")
    r.withdraw()
    yield r
    r.destroy()


def test_the_bar_shows_the_first_notice_and_a_details_dialog(root, monkeypatch):
    shown = []
    import molass_gui.error_dialog as error_dialog
    monkeypatch.setattr(error_dialog, "show_error_detail",
                        lambda win, status_var, message, title="", prefix="": shown.append((message, title)))
    win = tk.Toplevel(root)
    found = build_notices(7, 3, [LIBRARY_WARNING])
    bar = notices.NoticeBar(win, found)
    assert "Asked for 7 components, got 3." in bar.label.cget("text") and "+1 more" in bar.label.cget("text")
    bar.show_details()
    assert shown and "Asked for 7 components, got 3." in shown[0][0] and shown[0][1] == "Notices from molass"


def test_no_notices_no_bar(root):
    win = tk.Toplevel(root)
    assert notices.NoticeBar(win, []).frame is None and not win.winfo_children()


def test_rank2_notices_have_a_plain_first_line_then_the_library_texts():
    assert notices.rank2_notices([]) == [] and notices.rank2_notices(["", ""]) == []
    got = notices.rank2_notices(["B/A exceeds twice the hard-core envelope", "B/A exceeds twice the hard-core envelope", "K is small"])
    assert got[0].startswith("The interparticle (rank-2) correction") and got[1:] == ["B/A exceeds twice the hard-core envelope", "K is small"]


def test_the_bar_can_appear_change_and_go_after_the_window_was_opened(root):
    win = tk.Toplevel(root)
    hdr = tk.Frame(win)
    hdr.pack()
    bar = notices.NoticeBar(win, [])
    assert bar.frame is None
    bar.update(["first", "second"], after=hdr)
    assert bar.frame is not None and "first" in bar.label.cget("text") and "+1 more" in bar.label.cget("text")
    frame = bar.frame
    bar.update(["only"], after=hdr)
    assert bar.frame is frame and "only" in bar.label.cget("text") and "more" not in bar.label.cget("text")
    bar.update([])
    assert bar.frame is None and not frame.winfo_exists()


class RanksDecomp:
    """A decomposition whose rank-2 redraw warns or fails, as the library does (soft-bounded warnings, molass-library#421)."""

    def __init__(self, warn=None, error=None):
        self.xr_ranks, self.warn, self.error, self.ranks_set = None, warn, error, []

    def get_num_components(self):
        return 2

    def update_xr_ranks(self, ranks):
        self.xr_ranks = list(ranks)
        self.ranks_set.append(list(ranks))

    def plot_components(self, **kwargs):
        from matplotlib.figure import Figure
        if 2 in (self.xr_ranks or []):
            if self.error:
                raise ValueError(self.error)
            if self.warn:
                warnings.warn(self.warn, UserWarning)
        return SimpleNamespace(fig=Figure())


def _quick_view(root, decomp):
    from molass_gui import quick_view
    from molass_gui.session_context import SessionContext
    ctx = SessionContext("folder")
    view = quick_view.QuickView(decomp, None, 2, ctx, parent=root, app_root=SimpleNamespace(close_session=lambda: None), rgcurve="rg",
                                found_notices=["from the decomposition"], back=lambda rgcurve: None)
    view.show()
    return view, ctx


def test_applying_ranks_shows_what_the_library_says_and_keeps_the_notices_of_the_decomposition(root):
    view, ctx = _quick_view(root, RanksDecomp(warn="B/A exceeds twice the hard-core envelope"))
    assert view._notice_bar.notices == ["from the decomposition"]
    view._ranks_var.set("1,2")
    view._apply_ranks()
    shown = view._notice_bar.notices
    assert shown[0] == "from the decomposition" and shown[1].startswith("The interparticle (rank-2) correction") and shown[2] == "B/A exceeds twice the hard-core envelope"
    assert ctx.xr_ranks == [1, 2]
    view._ranks_var.set("1,1")                       # the rank-2 notices go with the rank-2 component
    view._apply_ranks()
    assert view._notice_bar.notices == ["from the decomposition"]


def test_a_rank2_component_without_the_stated_error_leaves_the_earlier_ranks_and_says_why(root):
    reason = "a rank-2 (interparticle) component needs the stated error xr.E, which is missing"
    decomp = RanksDecomp(error=reason)
    view, ctx = _quick_view(root, decomp)
    view._ranks_var.set("1,2")
    view._apply_ranks()
    assert reason in view._status_var.get() and view._status_var.get().startswith("Ranks not applied")
    assert decomp.xr_ranks == [1, 1] and ctx.xr_ranks is None          # back to the earlier ranks, the view still works
    assert view._notice_bar.notices == ["from the decomposition"]