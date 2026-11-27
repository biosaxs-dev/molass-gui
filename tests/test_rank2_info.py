"""molass-gui#26 (and #25): the one-line rank-2 summary leads with the impact; the findings come in plain language with what they affect and what to check."""
import tkinter as tk
import warnings
from types import SimpleNamespace

import pytest

from molass_gui import quick_view, rank2_info, rank2_report_dialog
from molass_gui.session_context import SessionContext

LIBRARY_TEXT = "B/A exceeds twice the hard-core envelope significantly at 65% of the points in the band 0.0707 <= q < 0.106: adhesive or soft particles?"


def finding(code="violation", text=LIBRARY_TEXT):
    return SimpleNamespace(code=code, text=text, plain="At mid q the data show more interparticle signal than a hard core can have.",
                           region="mid q, 0.0707-0.106 1/A", check="Compare the Rg with and without Ranks = 2.")


def entry(findings=(), rg=((35.22, 34.22), (30.31, 33.45))):
    names = ("adaptive (RgEstimator)", "from lowest q (q*Rg < 1.3)")
    return {"findings": list(findings), "warnings": [f.text for f in findings],
            "impact": {"rg": [dict(convention=n, uncorrected=u, corrected=c, change_pct=(c / u - 1) * 100) for n, (u, c) in zip(names, rg)], "shape": None}}


def test_the_summary_leads_with_the_impact_then_the_number_of_checks():
    text = rank2_info.fmt_rank2_summary({0: entry([finding(), finding("refine_at_bound", "x")])})
    assert text == ("Ranks = 2: Rg 35.2 -> 34.2 A (-2.8 %, adaptive fit); 30.3 -> 33.5 A (+10.4 %, from the lowest q) | 2 checks flagged (see the notice)")
    assert rank2_info.fmt_rank2_summary({0: entry([finding()])}).endswith("| 1 check flagged (see the notice)")
    assert rank2_info.fmt_rank2_summary({0: entry()}).endswith("| no checks flagged")


def test_no_report_no_summary_and_several_components_are_told_apart():
    assert rank2_info.fmt_rank2_summary(None) == "" and rank2_info.fmt_rank2_summary({}) == ""
    text = rank2_info.fmt_rank2_summary({0: entry(), 2: entry([finding()])})
    assert "component 1: Rg" in text and "component 3: Rg" in text and "no checks flagged" in text and "1 check flagged" in text


def test_an_older_report_without_impact_and_findings_still_gives_a_summary():
    old = {0: {"warnings": ["a", "b"], "rg_corrected": {"adaptive (RgEstimator)": {"Rg": 34.0}}, "rg_uncorrected": {"adaptive (RgEstimator)": {"Rg": 35.0}}}}
    text = rank2_info.fmt_rank2_summary(old)
    assert "35.0 -> 34.0 A (-2.9 %, adaptive fit)" in text and "2 checks flagged" in text


def test_a_component_that_was_not_corrected_says_so():
    assert "not corrected: no valid Rg seed" in rank2_info.fmt_rank2_summary({0: {"note": "no valid Rg seed", "warnings": []}})


def test_the_notices_carry_the_plain_text_what_it_affects_what_to_check_and_the_library_text():
    caught = [f"Soft-bounded LRF, component 0: {LIBRARY_TEXT} (see decomposition.soft_bounded_info)", "an unrelated warning"]
    out = rank2_info.build_rank2_notices(caught, {0: entry([finding()])})
    assert out[0].startswith("1 check of the interparticle (rank-2) correction flagged") and len(out[0]) < 120
    assert out[1].startswith("At mid q the data show") and "Affects: mid q, 0.0707-0.106 1/A." in out[1] and "Check: Compare the Rg" in out[1] and LIBRARY_TEXT in out[1]
    assert out[2:] == ["an unrelated warning", rank2_info.NOT_A_RISK_LEVEL]       # the warning the finding covers is not repeated; the note ends the list


def test_without_findings_the_generic_notices_stay():
    caught = ["B/A exceeds the envelope"]
    assert rank2_info.build_rank2_notices(caught, {0: {"warnings": caught}}) == rank2_info.notices.rank2_notices(caught)
    assert rank2_info.build_rank2_notices([], None) == []


class ReportDecomp:
    def __init__(self, report=None, fails=False):
        self.xr_ranks, self.report, self.fails = None, report, fails

    def get_num_components(self):
        return 2

    def update_xr_ranks(self, ranks):
        self.xr_ranks = list(ranks)

    def plot_components(self, **kwargs):
        from matplotlib.figure import Figure
        if 2 in (self.xr_ranks or []):
            warnings.warn(f"Soft-bounded LRF, component 0: {LIBRARY_TEXT} (see decomposition.soft_bounded_info)", UserWarning)
        return SimpleNamespace(fig=Figure())

    def rank2_report(self):
        if self.fails:
            raise RuntimeError("report failed")
        return self.report


class OldDecomp(ReportDecomp):
    """A decomposition of a molass without rank2_report."""
    rank2_report = property(lambda self: (_ for _ in ()).throw(AttributeError("rank2_report")))


@pytest.fixture
def root():
    try:
        r = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"no display: {exc}")
    r.withdraw()
    yield r
    r.destroy()


def _view(root, decomp):
    view = quick_view.QuickView(decomp, None, 2, SessionContext("folder"), parent=root, app_root=SimpleNamespace(close_session=lambda: None),
                                rgcurve="rg", back=lambda rgcurve: None)
    view.show()
    return view


def test_apply_puts_the_summary_in_the_status_line_and_the_findings_in_the_notice_bar(root):
    view = _view(root, ReportDecomp({0: entry([finding()])}))
    view._ranks_var.set("1,2")
    view._apply_ranks()
    assert view._rank2_line_var.get().startswith("Ranks = 2: Rg 35.2 -> 34.2 A") and "1 check flagged" in view._rank2_line_var.get()
    assert view._status_var.get() == "" and view._rank2_row.winfo_manager() == "pack"          # a row of its own, not the header
    notices_now = view._notice_bar.notices
    assert notices_now[0].startswith("1 check of the interparticle") and "Check: Compare the Rg" in notices_now[1] and notices_now[-1] == rank2_info.NOT_A_RISK_LEVEL and len(notices_now) == 3
    view._ranks_var.set("1,1")                                         # no rank-2 component: nothing left of it
    view._apply_ranks()
    assert view._rank2_line_var.get() == "" and view._rank2_row.winfo_manager() == "" and view._notice_bar.notices == []


@pytest.mark.parametrize("decomp_class, kwargs", [(ReportDecomp, dict(fails=True)), (OldDecomp, {})])
def test_a_failing_or_missing_report_never_breaks_applying_the_ranks(root, decomp_class, kwargs):
    view = _view(root, decomp_class(**kwargs))
    view._ranks_var.set("1,2")
    view._apply_ranks()
    assert view._ctx.xr_ranks == [1, 2] and view._status_var.get() == ""
    assert view._notice_bar.notices[0].startswith("The interparticle (rank-2) correction")       # the generic notice


class ReprReport(dict):
    def __repr__(self):
        return "component 0: soft_bounded\n  bound: K = 0.355"


def test_the_report_button_sits_with_the_summary_and_opens_the_text_with_a_working_copy(root):
    view = _view(root, ReportDecomp(ReprReport({0: entry([finding()])})))
    view._ranks_var.set("1,2")
    view._apply_ranks()
    assert view._rank2_row.winfo_manager() == "pack" and view._rank2_tools.winfo_manager() == "pack"       # in the rank row: the header keeps its width
    buttons = [w for w in view._rank2_tools.winfo_children() if w.winfo_class() == "TButton"]
    assert [b.cget("text") for b in buttons] == ["Rank-2 report\u2026"] and buttons[0] is view._rank2_report_btn
    opened = []
    real = rank2_report_dialog.show_rank2_report
    rank2_report_dialog.show_rank2_report = lambda win, text, heading=None, title="Rank-2 report": opened.append(real(win, text, heading, title))
    try:
        buttons[0].invoke()
    finally:
        rank2_report_dialog.show_rank2_report = real
    dlg = opened[0]
    assert dlg.title() == "Rank-2 report" and dlg.text_widget.get("1.0", "end-1c") == "component 0: soft_bounded\n  bound: K = 0.355"
    assert str(dlg.text_widget.cget("state")) == "disabled"
    dlg.copy()
    assert dlg.clipboard_get() == "component 0: soft_bounded\n  bound: K = 0.355"
    view._ranks_var.set("1,1")                                         # without a rank-2 component the button goes with the row
    view._apply_ranks()
    assert view._rank2_tools.winfo_manager() == "" and view._rank2_row.winfo_manager() == "" and view._rank2_report_text == ""    # no second direction in this fake: the row goes


def test_the_report_text_is_empty_without_a_report():
    assert rank2_report_dialog.report_text(None) == "" and rank2_report_dialog.report_text({}) == ""


class MethodDecomp(ReportDecomp):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.methods = []

    def set_rank2_method(self, method):
        self.methods.append(method)


def _method_boxes(view):
    return [w for w in view._rank2_tools.winfo_children() if w.winfo_class() == "TCombobox"]


def test_the_method_choice_is_hidden_unless_develop_and_a_molass_that_has_it(root, monkeypatch):
    from molass_gui import feature_flags
    monkeypatch.setattr(feature_flags, "DEVELOP_MODE_ENABLED", False)
    assert _method_boxes(_view(root, MethodDecomp({0: entry()}))) == []
    monkeypatch.setattr(feature_flags, "DEVELOP_MODE_ENABLED", True)
    assert _method_boxes(_view(root, ReportDecomp({0: entry()}))) == []        # a molass without set_rank2_method
    assert len(_method_boxes(_view(root, MethodDecomp({0: entry()})))) == 1


def test_choosing_the_bounded_method_sets_it_applies_the_ranks_again_and_is_kept_in_the_context(root, monkeypatch):
    from molass_gui import feature_flags
    monkeypatch.setattr(feature_flags, "DEVELOP_MODE_ENABLED", True)
    decomp = MethodDecomp({0: entry([finding()])})
    view = _view(root, decomp)
    view._ranks_var.set("1,2")
    view._apply_ranks()
    assert view._rank2_method_var.get() == "soft-bounded" and view._ctx.rank2_method is None
    decomp.ranks_set = []
    view._rank2_method_var.set("bounded (clip)")
    view._on_rank2_method_change()
    assert decomp.methods == ["bounded"] and view._ctx.rank2_method == "bounded" and decomp.xr_ranks == [1, 2]
    assert view._rank2_line_var.get().startswith("Ranks = 2:")                   # the plots, summary and notices were made again
    view._rank2_method_var.set("soft-bounded")
    view._on_rank2_method_change()
    assert decomp.methods == ["bounded", "soft_bounded"] and view._ctx.rank2_method is None


def test_the_chosen_method_is_exported_only_with_a_rank2_component():
    import molass_data
    from molass_gui.notebook_export import build_notebook
    ctx = SessionContext(molass_data.SAMPLE1)
    ctx.num_components = 3
    source = lambda: "\n".join(c.source for c in build_notebook(ctx).cells if c.cell_type == "code")
    ctx.xr_ranks, ctx.rank2_method = [1, 2, 1], None
    assert "\ndecomp.set_rank2_method(" not in source()                                   # the library default needs no line
    ctx.rank2_method = "bounded"
    assert "decomp.update_xr_ranks([1, 2, 1])\ndecomp.set_rank2_method('bounded')\n" in source()
    ctx.xr_ranks = [1, 1, 1]
    assert "\ndecomp.set_rank2_method(" not in source()
    ctx.forget_decomposition()
    assert ctx.rank2_method is None

class SecondDirectionDecomp(ReportDecomp):
    """A decomposition of a molass that has second_direction_report()."""

    def __init__(self, n=1, text="second direction report (fake)", fails=None):
        super().__init__(None)
        self.n, self.text, self.fails, self.calls = n, text, fails, 0

    def get_num_components(self):
        return self.n

    def second_direction_report(self):
        self.calls += 1
        if self.fails:
            raise ValueError(self.fails)
        return _TextReport(self.text)


class _TextReport:
    """Like the library's report objects: the text is its repr."""

    def __init__(self, text):
        self.text = text

    def __repr__(self):
        return self.text


def _open_dialogs(monkeypatch):
    opened = []
    real = rank2_report_dialog.show_rank2_report
    monkeypatch.setattr(rank2_report_dialog, "show_rank2_report", lambda win, text, heading=None, title="Rank-2 report": opened.append(real(win, text, heading, title)))
    return opened


def test_the_second_direction_button_is_in_the_rank_row_from_the_start_for_one_component(root, monkeypatch):
    view = _view(root, SecondDirectionDecomp())
    assert view._rank2_row.winfo_manager() == "pack" and view._second_dir_btn.winfo_manager() == "pack"
    assert view._rank2_tools.winfo_manager() == ""                     # the rank-2 tools wait for a rank-2 component
    opened = _open_dialogs(monkeypatch)
    view._second_dir_btn.invoke()
    assert opened and opened[0].title() == "Second-direction report" and opened[0].text_widget.get("1.0", "end-1c") == "second direction report (fake)"
    opened[0].copy()
    assert opened[0].clipboard_get() == "second direction report (fake)"


def test_the_second_direction_button_needs_one_component_and_a_molass_that_has_the_report(root):
    assert _view(root, SecondDirectionDecomp(n=2))._rank2_row.winfo_manager() == ""      # several components: the report is defined for one (frames= is not in this version)
    assert _view(root, ReportDecomp(None))._rank2_row.winfo_manager() == ""               # an older molass without second_direction_report


def test_the_second_direction_button_stays_when_ranks_are_applied_and_does_not_depend_on_them(root, monkeypatch):
    decomp = SecondDirectionDecomp()
    view = _view(root, decomp)
    view._ranks_var.set("1,2")
    view._apply_ranks()
    assert view._second_dir_btn.winfo_manager() == "pack"
    view._ranks_var.set("1,1")
    view._apply_ranks()
    assert view._rank2_row.winfo_manager() == "pack" and view._second_dir_btn.winfo_manager() == "pack"       # the row stays without a rank-2 component
    opened = _open_dialogs(monkeypatch)
    view._second_dir_btn.invoke()
    assert decomp.calls == 1 and opened


def test_a_failing_second_direction_report_is_shown_not_raised(root, monkeypatch):
    import molass_gui.error_dialog as error_dialog
    shown = []
    monkeypatch.setattr(error_dialog, "show_error_detail", lambda win, status_var, message, title="", prefix="": shown.append((message, title)))
    view = _view(root, SecondDirectionDecomp(fails="the second-direction report needs the stated error xr.E, which is missing"))
    view._second_dir_btn.invoke()
    assert shown and "stated error" in shown[0][0] and shown[0][1] == "Second direction failed"