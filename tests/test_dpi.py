"""High-DPI support: the scale factor reaches Tk, matplotlib and the sizes written in pixels."""
import matplotlib
import pytest

from molass_gui import dpi


class _Tk:
    def __init__(self):
        self.scaling = None

    def call(self, *args):
        assert args[:2] == ("tk", "scaling")
        self.scaling = args[2]


class _Root:
    def __init__(self, pixels_per_inch):
        self.ppi = pixels_per_inch
        self.tk = _Tk()

    def winfo_fpixels(self, spec):
        assert spec == "1i"
        return self.ppi


@pytest.fixture
def restore():
    saved = dict(matplotlib.rcParams), dpi._factor, dpi._requested
    yield
    matplotlib.rcParams.update(saved[0])
    dpi._factor, dpi._requested = saved[1], saved[2]


@pytest.mark.parametrize("text, value", [("auto", None), ("AUTO", None), ("1", 1.0), ("1.25", 1.25), (" 0.8 ", 0.8)])
def test_parse_ui_scale(text, value):
    assert dpi.parse_ui_scale(text) == value


@pytest.mark.parametrize("text", ["big", "0.1", "9", ""])
def test_a_bad_ui_scale_is_rejected(text):
    with pytest.raises(ValueError):
        dpi.parse_ui_scale(text)


def test_the_default_is_compact_whatever_the_system_scaling(restore):
    root = _Root(144.0)                                  # a 4K screen at 150 %
    assert dpi.init(root) == 1.0
    assert dpi.px(1000) == 1000 and dpi.geometry(1000, 820) == "1000x820"
    assert matplotlib.rcParams["figure.dpi"] == 100.0
    assert root.tk.scaling == pytest.approx(96.0 / 72.0)   # the Tk fonts as on a 100 % display


def test_auto_follows_the_system_scaling(restore):
    dpi.set_ui_scale("auto")
    root = _Root(144.0)
    assert dpi.init(root) == 1.5
    assert dpi.px(1000) == 1500 and dpi.geometry(1000, 820) == "1500x1230"
    assert matplotlib.rcParams["figure.dpi"] == 150.0
    assert matplotlib.rcParams["savefig.dpi"] == 100.0      # exported images keep their size
    assert root.tk.scaling == pytest.approx(2.0)


def test_a_chosen_scale_applies_to_everything(restore):
    dpi.set_ui_scale("1.25")
    root = _Root(96.0)
    assert dpi.init(root) == 1.25
    assert dpi.px(800) == 1000 and matplotlib.rcParams["figure.dpi"] == 125.0
    assert root.tk.scaling == pytest.approx(96.0 * 1.25 / 72.0)


def test_auto_on_a_screen_below_96_dpi_is_not_shrunk(restore):
    dpi.set_ui_scale("auto")
    assert dpi.init(_Root(72.0)) == 1.0
