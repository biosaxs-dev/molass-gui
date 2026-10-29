"""The rigorous view shows rejected (non-finite) iterations and a stalled search (molass-library#346)."""
import pytest

pytest.importorskip("tkinter")
from molass_gui.rigorous_view import _fmt_quality_info


def test_nothing_to_report():
    assert _fmt_quality_info(0, 66, 0) == ("", False)
    assert _fmt_quality_info(None, None, None) == ("", False)    # a molass without these fields
    assert _fmt_quality_info(0, 66, 1) == ("", False)             # one job without improvement is normal


def test_few_rejected_iterations_are_shown_without_warning():
    assert _fmt_quality_info(6, 66, 0) == ("Rejected: 6/66", False)


def test_many_rejected_iterations_warn():
    text, warn = _fmt_quality_info(20, 66, 0)
    assert text == "Rejected: 20/66" and warn


def test_stalled_search_warns():
    text, warn = _fmt_quality_info(0, 66, 2)
    assert text == "no improvement in the last 2 jobs" and warn


def test_both():
    text, warn = _fmt_quality_info(11, 66, 3)
    assert text == "Rejected: 11/66  no improvement in the last 3 jobs" and warn


def test_unknown_total():
    assert _fmt_quality_info(3, None, 0) == ("Rejected: 3", False)
