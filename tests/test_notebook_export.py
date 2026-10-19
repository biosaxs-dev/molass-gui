"""The exported notebook must load bundled sample data via molass_data, not an absolute path."""
import pytest

molass_data = pytest.importorskip("molass_data")

from molass_gui.notebook_export import build_notebook
from molass_gui.session_context import SessionContext, to_sample_name


def _first_code_source(ctx):
    nb = build_notebook(ctx)
    return next(c.source for c in nb.cells if c.cell_type == "code")


def test_sample_folder_is_recognized():
    assert to_sample_name(molass_data.SAMPLE1) == "SAMPLE1"
    assert to_sample_name(molass_data.SAMPLE1 + "\\") == "SAMPLE1"
    assert to_sample_name("C:/some/other/folder") is None


def test_export_uses_molass_data_for_samples():
    src = _first_code_source(SessionContext(molass_data.SAMPLE1))
    assert "import molass_data" in src
    assert "SSD(molass_data.SAMPLE1)" in src
    assert molass_data.SAMPLE1 not in src


def test_export_keeps_uv_pickat_for_samples():
    ctx = SessionContext(molass_data.SAMPLE1)
    ctx.uv_pickat = 300
    assert "SSD(molass_data.SAMPLE1, uv_pickat=300)" in _first_code_source(ctx)


def test_export_of_custom_folder_keeps_the_path(tmp_path):
    src = _first_code_source(SessionContext(str(tmp_path)))
    assert f'SSD(r"{tmp_path}")' in src
    assert "molass_data" not in src
