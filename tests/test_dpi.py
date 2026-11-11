"""High-DPI support: the scale factor reaches matplotlib and the sizes written in pixels."""
import matplotlib
import pytest

from molass_gui import dpi


class _Root:
    def __init__(self, pixels_per_inch):
        self.ppi = pixels_per_inch

    def winfo_fpixels(self, spec):
        assert spec == "1i"
        return self.ppi


@pytest.fixture
def restore():
    saved = dict(matplotlib.rcParams), dpi._factor
    yield
    matplotlib.rcParams.update(saved[0])
    dpi._factor = saved[1]


def test_at_150_percent_sizes_and_figures_scale(restore):
    assert dpi.init(_Root(144.0)) == 1.5
    assert dpi.px(1000) == 1500 and dpi.geometry(1000, 820) == "1500x1230"
    assert matplotlib.rcParams["figure.dpi"] == 150.0
    assert matplotlib.rcParams["savefig.dpi"] == 100.0      # exported images keep their size


def test_at_100_percent_nothing_changes(restore):
    before = matplotlib.rcParams["figure.dpi"]
    assert dpi.init(_Root(96.0)) == 1.0
    assert dpi.px(1000) == 1000 and dpi.geometry(640, 320) == "640x320"
    assert matplotlib.rcParams["figure.dpi"] == before


def test_a_screen_below_96_dpi_is_not_shrunk(restore):
    assert dpi.init(_Root(72.0)) == 1.0
