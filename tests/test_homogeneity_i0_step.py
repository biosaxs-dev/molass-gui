"""The background I(0) step of the Homogeneity dialog (no Tk needed: a fake window runs ``after`` inline)."""
import time
from types import SimpleNamespace

import numpy as np
import pytest

pytest.importorskip("molass.Homogeneity.Report")
from molass_gui.homogeneity_dialog import _with_i0


class FakeWin:
    def after(self, ms, fn):
        time.sleep(0.01)
        fn()


class FakeVar:
    def __init__(self):
        self.value = "idle"
        self.history = []

    def get(self):
        return self.value

    def set(self, v):
        self.value = v
        self.history.append(v)


def _rg(i0s):
    return SimpleNamespace(i0s=np.asarray(i0s, dtype=float))


def test_rgcurve_with_i0_is_used_directly():
    seen, status = [], FakeVar()
    rg = _rg([1.0, 2.0])
    _with_i0(FakeWin(), status, SimpleNamespace(), rg, seen.append)
    assert seen == [rg] and status.history == []


def test_rgcurve_without_i0_is_completed_in_the_background():
    good = _rg([1.0, 2.0])
    calls = []

    def compute():
        calls.append(1)
        time.sleep(0.05)
        return good

    ssd = SimpleNamespace(xr=SimpleNamespace(compute_rgcurve=compute))
    seen, status = [], FakeVar()
    _with_i0(FakeWin(), status, ssd, _rg([np.nan, np.nan]), seen.append)
    assert seen == [good] and calls == [1]
    assert "Computing I(0)" in status.history[0] and status.value == "idle"
    # cached on the ssd: a second call does not compute again
    seen.clear()
    _with_i0(FakeWin(), status, ssd, _rg([np.nan]), seen.append)
    assert seen == [good] and calls == [1]
