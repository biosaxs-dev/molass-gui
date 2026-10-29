"""The GUI shows the angular range, offers the low-q trimming choice and hints at rank 2 (molass-library#342)."""
from types import SimpleNamespace

import numpy as np
import pytest

from molass_gui.trimming_info import (
    SMALL_ANGLE_LIMITS, fmt_interparticle_hint, fmt_qrange, small_angle_limit_from_label, trim_kwargs,
)


def _ssd(q):
    return SimpleNamespace(xr=SimpleNamespace(qv=np.asarray(q)))


def test_labels_map_to_library_values():
    assert [small_angle_limit_from_label(label) for label, _ in SMALL_ANGLE_LIMITS] == [None, "extended", "guinier", "none"]
    assert small_angle_limit_from_label("something else") is None


def test_trim_kwargs_omit_the_library_default():
    assert trim_kwargs(None) == {}
    assert trim_kwargs("guinier") == {"small_angle_limit": "guinier"}


def test_qrange_tells_how_many_low_q_points_were_cut():
    raw = np.linspace(0.0075, 0.4, 100)
    text = fmt_qrange(_ssd(raw), _ssd(raw[4:]))
    assert text.startswith("q: 0.0234") and "(4 lowest-q points cut)" in text


def test_qrange_when_nothing_is_cut():
    raw = np.linspace(0.0075, 0.4, 100)
    assert "all low-q points kept" in fmt_qrange(_ssd(raw), _ssd(raw))


def test_qrange_is_empty_when_it_cannot_be_told():
    assert fmt_qrange(SimpleNamespace(xr=None), SimpleNamespace(xr=None)) == ""


def test_interparticle_hint():
    assert "Ranks = 2" in fmt_interparticle_hint({"num_components": 1, "ranks": [2]})
    assert fmt_interparticle_hint({"num_components": 3}) == ""
    assert fmt_interparticle_hint({"ranks": [1, 1]}) == ""
    assert fmt_interparticle_hint(None) == ""


def test_fronting_text():
    from types import SimpleNamespace
    from molass_gui.trimming_info import fmt_fronting

    def decomp(model, taus, flags=None):
        curves = [SimpleNamespace(model=model, get_params=lambda t=t: [1.0, 100.0, 20.0, t]) for t in taus]
        return SimpleNamespace(xr_ccurves=curves, num_components=len(taus), fronting_flags=flags)

    assert fmt_fronting(decomp('egh', [-7.5])) == "Fronting allowed: all"           # detected from the EGH fit
    assert fmt_fronting(decomp('egh', [0.0, 3.0])) == "Fronting allowed: none"
    assert fmt_fronting(decomp('edm', [0.0, 0.0, 0.0], flags=[False, False, True])) == "Fronting allowed: component 3"
    assert fmt_fronting(decomp('sdm', [0.0])) == ""                                   # cannot front
    assert fmt_fronting(object()) == ""                                               # not a decomposition


def test_export_carries_the_chosen_limit():
    molass_data = pytest.importorskip("molass_data")
    from molass_gui.notebook_export import build_notebook
    from molass_gui.session_context import SessionContext

    def trimming_line(limit):
        ctx = SessionContext(molass_data.SAMPLE1)
        ctx.small_angle_limit = limit
        nb = build_notebook(ctx)
        src = next(c.source for c in nb.cells if c.cell_type == "code")
        return next(line for line in src.splitlines() if line.startswith("trimmed ="))

    assert trimming_line(None) == "trimmed = ssd.trimmed_copy()"
    assert trimming_line("guinier") == "trimmed = ssd.trimmed_copy(small_angle_limit='guinier')"
