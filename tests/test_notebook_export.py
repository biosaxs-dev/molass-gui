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


def test_benchmark_samples_are_exported_through_molass_benchmarks():
    molass_benchmarks = pytest.importorskip("molass_benchmarks")
    from molass_gui.session_context import iter_samples, sample_path, to_sample_ref
    assert to_sample_ref(molass_benchmarks.PROTEINS5) == ("molass_benchmarks", "PROTEINS5")
    assert sample_path("PROTEINS5") == molass_benchmarks.PROTEINS5
    assert "PROTEINS5" in [name for _, name, _ in iter_samples()]
    src = _first_code_source(SessionContext(molass_benchmarks.PROTEINS5))
    assert "import molass_benchmarks" in src
    assert "SSD(molass_benchmarks.PROTEINS5)" in src
    assert molass_benchmarks.PROTEINS5 not in src


def test_export_of_chosen_peak_positions():
    ctx = SessionContext(molass_data.SAMPLE1)
    ctx.num_components = 3
    ctx.xr_peakpositions = [561, 648, 760]
    decomp_cell = next(c.source for c in build_notebook(ctx).cells
                       if c.cell_type == "code" and "quick_decomposition" in c.source)
    assert "quick_decomposition(xr_peakpositions=[561, 648, 760]" in decomp_cell
    assert "num_components" not in decomp_cell
    ctx.xr_peakpositions = None
    decomp_cell = next(c.source for c in build_notebook(ctx).cells
                       if c.cell_type == "code" and "quick_decomposition" in c.source)
    assert "quick_decomposition(num_components=3" in decomp_cell


def test_export_has_the_mass_cell_with_its_caveat_after_the_decomposition():
    ctx = SessionContext(molass_data.SAMPLE1)
    ctx.num_components = 3
    codes = [c.source for c in build_notebook(ctx).cells if c.cell_type == "code"]
    i = next(i for i, c in enumerate(codes) if "quick_decomposition" in c)
    mass = codes[i + 1]
    assert "decomp.get_xr_components()" in mass and "comp.get_volume_mass()" in mass
    assert "corrected.get_volume_mass_curve().plot()" in mass
    assert "protein calibration" in mass or "0.77-0.95" in mass
    ctx.model_info = {"model": "sdm"}
    mass = next(c for c in (c.source for c in build_notebook(ctx).cells) if "get_volume_mass()" in c)
    assert "decomp_sdm.get_xr_components()" in mass          # the active (upgraded) decomposition
    ctx.num_components = None
    assert not any("get_volume_mass" in c.source for c in build_notebook(ctx).cells)


@pytest.fixture
def anomaly_handling_off():
    from molass.Global.Options import get_molass_options, set_molass_options
    before = get_molass_options('anomaly_handling')
    set_molass_options(anomaly_handling=False)
    yield
    set_molass_options(anomaly_handling=before)


def test_export_has_no_option_line_by_default():
    from molass.Global.Options import get_molass_options, set_molass_options
    before = get_molass_options('anomaly_handling')
    set_molass_options(anomaly_handling=True)
    try:
        assert "set_molass_options" not in _first_code_source(SessionContext(molass_data.SAMPLE1))
    finally:
        set_molass_options(anomaly_handling=before)


def test_export_reflects_switched_off_anomaly_handling(anomaly_handling_off):
    src = _first_code_source(SessionContext(molass_data.SAMPLE1))
    assert "set_molass_options(anomaly_handling=False)" in src
    assert src.index("set_molass_options") < src.index("SSD(molass_data.SAMPLE1)")   # before the trimming


def test_restore_notebook_reflects_switched_off_anomaly_handling(anomaly_handling_off):
    from molass_gui.notebook_export import build_restore_notebook
    nb = build_restore_notebook("some/analysis")
    src = next(c.source for c in nb.cells if c.cell_type == "code")
    assert src.startswith("from molass.Global.Options import set_molass_options")
    assert "rebuild_decomposition_from_recipe(analysis_folder)" in src
