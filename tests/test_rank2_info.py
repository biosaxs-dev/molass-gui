"""molass-gui#26 (and #25): the one-line rank-2 summary leads with the impact; the findings come in plain language with what they affect and what to check."""
import tkinter as tk
import warnings
from types import SimpleNamespace

import pytest

from molass_gui import quick_view, rank2_info
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
