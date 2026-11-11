"""molass-gui#13: the Mass dialog -- logic without Tk, the dialog headless, and one run on simulated data."""
import math
import tkinter as tk
from types import SimpleNamespace

import numpy as np
import pytest

from molass_gui import mass_logic
from molass_gui.mass_logic import fmt_mass, round_figures, component_rows, compute_mass, window_title


@pytest.mark.parametrize("value, text", [(449.6, "450"), (35.7, "36"), (153.2, "150"), (1.234, "1.2"),
                                          (1234.0, "1200"), (0.0, "0"), (float("nan"), "n/a"), (None, "n/a")])
def test_masses_are_shown_to_two_figures(value, text):
    assert fmt_mass(value) == text
    assert round_figures(449.6) == 450


def test_window_title_names_the_stage():
    assert window_title("Quick") == "Mass \u2014 Quick" and window_title(None) == "Mass"


class _Vm:
    def __init__(self, mass, rg, reason=None):
        self.mass, self.rg, self.reason = mass, rg, reason

    def __bool__(self):
        return math.isfinite(self.mass)


class _Component:
    def __init__(self, vm=None, error=None):
        self.vm, self.error = vm, error

    def get_volume_mass(self):
        if self.error:
            raise self.error
        return self.vm


def test_component_rows_say_why_a_mass_is_missing():
    rows = component_rows([_Component(_Vm(449.6, 69.93)),
                           _Component(_Vm(float("nan"), 40.3, "only 12 points below q = 0.3, at least 20 needed")),
                           _Component(error=ValueError("no Guinier fit"))])
    assert rows[0] == (1, "69.9", "450", "")
    assert rows[1] == (2, "40.3", "n/a", "only 12 points below q = 0.3, at least 20 needed")
    assert rows[2] == (3, "n/a", "n/a", "no Guinier fit")


def test_the_caveat_names_the_limits():
    assert "0.77-0.95" in mass_logic.CAVEAT and "non-compact" in mass_logic.CAVEAT


def test_compute_mass_reports_why_the_curve_is_missing(monkeypatch):
    decomp = SimpleNamespace(get_xr_components=lambda: [_Component(_Vm(100.0, 30.0))], ssd=None)
    rows, curve, error = compute_mass(decomp)       # ssd=None: the curve cannot be made
    assert rows == [(1, "30.0", "100", "")] and curve is None and error


@pytest.fixture
def root():
    try:
        r = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"no display: {exc}")
    r.withdraw()
    yield r
    r.destroy()


class _Curve:
    def plot(self, ax=None, **kwargs):
        ax.plot([1, 2, 3], [10, 20, 30])


def test_dialog_shows_table_caveat_and_curve(root):
    from molass_gui.mass_dialog import MassDialog
    dlg = MassDialog(root, [(1, "69.9", "450", ""), (2, "40.3", "n/a", "no valid Rg")], _Curve(), None,
                     stage="Quick", heading="data | EGH | quick")
    assert [dlg._tree.item(i, "values")[2] for i in dlg._tree.get_children()] == ["450", "n/a"]
    labels = [w.cget("text") for w in dlg._dlg.winfo_children() if w.winfo_class() == "TLabel"]
    assert mass_logic.CAVEAT in labels
    dlg._close()


def test_dialog_without_curve_still_shows_the_table_and_the_reason(root):
    from molass_gui.mass_dialog import MassDialog
    dlg = MassDialog(root, [(1, "69.9", "450", "")], None, "no frame has a reliable Guinier fit")
    texts = [w.cget("text") for f in dlg._dlg.winfo_children() for w in ([f] + f.winfo_children())
             if w.winfo_class() == "TLabel"]
    assert any("per-frame curve is not available: no frame" in t for t in texts)
    dlg._close()


def test_masses_of_a_simulated_decomposition(monkeypatch):
    """The real library API: a mass per component, and the curve on the frames of the data. The per-frame Rg curve
    (about 40 s on this data) is replaced by a flat one: its computation is tested in molass-library."""
    import warnings
    from molass.Testing import simulate_sample4_like
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        corrected = simulate_sample4_like().trimmed_copy().corrected_copy()
        decomp = corrected.quick_decomposition(num_components=2)
        frames = np.asarray(corrected.xr.jv)
        i0s = np.asarray(corrected.xr.M[:5].mean(axis=0), dtype=float)
        flat = SimpleNamespace(frames=frames, rgs=np.full(len(frames), 30.0), i0s=i0s,
                               scores=np.ones(len(frames)))
        rows, curve, error = compute_mass(decomp, rgcurve=flat)
    assert error is None and len(rows) == 2
    assert all(r[2] != "n/a" for r in rows)
    assert len(curve.frames) > 0 and np.isfinite(curve.mass).all()
