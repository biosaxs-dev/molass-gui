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
