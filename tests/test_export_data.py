"""Export Data: the chosen format reaches Decomposition.export(); old molass falls back."""
import pytest

from molass_gui import plot_embed


class _NewResult:
    def export(self, folder, fmt='dat', rgcurve=None):
        self.call = (folder, fmt, rgcurve)
        return ['a', 'b']


class _OldResult:
    def export_xr_components(self, folder):
        self.call = folder
        return ['a']


@pytest.fixture
def messages(monkeypatch):
    shown = []
    monkeypatch.setattr(plot_embed.messagebox, "showinfo", lambda *a, **k: shown.append(("info", a)))
    monkeypatch.setattr(plot_embed.messagebox, "showerror", lambda *a, **k: shown.append(("error", a)))
    return shown


def test_chosen_format_is_passed_through(monkeypatch, messages):
    monkeypatch.setattr(plot_embed, "ask_export_options", lambda parent: ("out", "csv"))
    result, rgcurve = _NewResult(), object()
    plot_embed.export_component_data(result, None, rgcurve=rgcurve)
    assert result.call == ("out", "csv", rgcurve)
    assert messages[0][0] == "info"


def test_cancel_exports_nothing(monkeypatch, messages):
    monkeypatch.setattr(plot_embed, "ask_export_options", lambda parent: None)
    result = _NewResult()
    plot_embed.export_component_data(result, None)
    assert not hasattr(result, "call")
    assert messages == []


def test_old_molass_falls_back_to_components_only(monkeypatch, messages):
    monkeypatch.setattr(plot_embed, "ask_export_options", lambda parent: ("out", "csv"))
    result = _OldResult()
    plot_embed.export_component_data(result, None)
    assert result.call == "out"
    assert messages[0][0] == "info"
