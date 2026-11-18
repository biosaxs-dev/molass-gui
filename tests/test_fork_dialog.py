"""Continue as new analysis... (molass-library#396): the rules of the dialog, the dialog itself and the launch path of a
fork, headless on fake plans. The library parts (plan_fork, fork_source, the seed) are tested in molass-library."""
import os
import time
import tkinter as tk
from types import SimpleNamespace

import pytest

from molass_gui import fork_dialog, fork_logic


# -- the rules (no Tk) --------------------------------------------------------------------------------------

def test_the_models_offered_start_with_the_one_of_the_source():
    assert fork_logic.model_choices("egh") == ["egh", "sdm", "edm", "lkm", "grm"]
    assert fork_logic.model_choices("grm") == ["grm", "sdm", "edm", "lkm"]       # a fork never goes back to EGH
    assert fork_logic.model_choices(None) == ["egh", "sdm", "edm", "lkm", "grm"]


def test_match_curves_is_for_a_change_to_grm_or_lkm_only():
    assert fork_logic.match_available("egh", "grm") and fork_logic.match_available("egh", "lkm")
    assert not fork_logic.match_available("egh", "sdm") and not fork_logic.match_available("egh", "edm")
    assert not fork_logic.match_available("grm", "grm")


def test_the_suggested_folder_is_free_and_named_after_the_model(tmp_path):
    source = str(tmp_path / "analysis-EGH")
    assert fork_logic.default_new_folder(source, "grm", "egh") == str(tmp_path / "analysis-EGH-GRM")
    assert fork_logic.default_new_folder(source, "egh", "egh") == str(tmp_path / "analysis-EGH-fork")
    os.makedirs(tmp_path / "analysis-EGH-GRM")
    assert fork_logic.default_new_folder(source, "grm", "egh") == str(tmp_path / "analysis-EGH-GRM-2")


def test_the_new_folder_must_be_a_new_place_for_an_analysis(tmp_path):
    source = str(tmp_path / "src")
    assert fork_logic.check_new_folder(str(tmp_path / "new"), source) is None
    assert "Give the folder" in fork_logic.check_new_folder("  ", source)
    assert "Resume" in fork_logic.check_new_folder(source, source)
    os.makedirs(tmp_path / "taken" / "optimized")
    assert "already holds an analysis" in fork_logic.check_new_folder(str(tmp_path / "taken"), source)
    (tmp_path / "file").write_text("x")
    assert "file" in fork_logic.check_new_folder(str(tmp_path / "file"), source)
    assert "does not exist" in fork_logic.check_new_folder(str(tmp_path / "nowhere" / "new"), source)


def test_fields_are_checked_together(tmp_path):
    new = str(tmp_path / "new")
    assert fork_logic.check_fields("egh", "grm", True, new) is None
    assert "GRM or LKM" in fork_logic.check_fields("egh", "sdm", True, new)
    assert "GRM or LKM" in fork_logic.check_fields("grm", "grm", True, new)
    assert "cannot change the model to EGH" in fork_logic.check_fields("grm", "egh", False, new)


def _plan(**overrides):
    plan = SimpleNamespace(
        model="grm", source_model="egh", seeded_from="best EGH of src (job 008) converted to GRM, curves matched",
        decomposition=SimpleNamespace(match_curves_info=dict(start_error=0.043, error=0.005, improved=True)),
        recipe={"method": "bh"}, new_folder="C:/x/new",
        kwargs=dict(seed_params=[1.0, 2.0], seed_source="s", note="n", function_code=None, frozen_components=None,
                    frozen_param_groups=[0], rgcurve="big", analysis_folder="C:/x/new", async_=True))
    plan.__dict__.update(overrides)
    return plan


def test_the_preview_says_what_job_000_starts_from():
    text = "\n".join(fork_logic.summary_lines(_plan(), SimpleNamespace(sv=73.75, fv=-1.2598), -1.5403, 81.95))
    assert "EGH \u2192 GRM" in text and "converted to GRM, curves matched" in text
    assert "0.043 \u2192 0.005" in text and "SV 73.75 (fv -1.2598)" in text and "SV 81.95" in text
    same = fork_logic.summary_lines(_plan(model="egh", seeded_from="best of src (job 008)",
                                          decomposition=SimpleNamespace(match_curves_info=None)),
                                    SimpleNamespace(sv=81.95, fv=-1.5403))
    assert "unchanged" in same[0] and not any("matched" in line for line in same)


def test_the_run_gets_the_seed_and_what_the_plan_fixed_but_nothing_else():
    extras = fork_logic.optimize_extras(_plan())
    assert extras == dict(seed_params=[1.0, 2.0], seed_source="s", note="n", frozen_param_groups=[0])


# -- the dialog ----------------------------------------------------------------------------------------------

@pytest.fixture
def root():
    try:
        r = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"no display: {exc}")
    r.withdraw()
    yield r
    r.destroy()


def pump(root, seconds=0.2):
    end = time.time() + seconds
    while time.time() < end:
        root.update()
        time.sleep(0.01)


def enabled(widget):
    return not widget.instate(["disabled"])


class FakeLibrary:
    """Stands for molass.Rigorous.ForkAnalysis: records the call of plan_fork, returns a fake plan."""

    def __init__(self):
        self.calls = []

    def plan_fork(self, source_folder, new_folder, **kwargs):
        self.calls.append((source_folder, new_folder, kwargs))
        plan = _plan(new_folder=new_folder, info=SimpleNamespace(fv=-1.54, sv=81.95))
        plan.recipe = {"method": kwargs["method"].lower()}
        plan.score = lambda: SimpleNamespace(sv=73.75, fv=-1.2598)
        return plan


@pytest.fixture
def library(monkeypatch):
    import molass.Rigorous.ForkAnalysis as fa
    fake = FakeLibrary()
    monkeypatch.setattr(fa, "plan_fork", fake.plan_fork)
    monkeypatch.setattr(fa, "fork_source", lambda *a, **k: SimpleNamespace(fv=-1.54, sv=81.95))
    return fake


def _dialog(root, tmp_path, started):
    ctx = fork_dialog.ForkContext(str(tmp_path / "analysis-EGH"), object(), object(),
                                  {"model": "egh", "method": "bh"})
    dlg = fork_dialog.ForkDialog(root, tk.StringVar(), ctx, lambda *a: started.append(a), jobs_default=4)
    dlg.show()
    pump(root)
    return dlg


def test_the_dialog_prepares_a_plan_and_starts_it_only_after_that(root, tmp_path, library):
    started = []
    dlg = _dialog(root, tmp_path, started)
    assert dlg._folder_var.get() == str(tmp_path / "analysis-EGH-SDM")      # the first change offered
    assert not enabled(dlg._start_btn)
    dlg._start()
    assert started == []                                                      # nothing prepared: nothing starts

    dlg._model_var.set("GRM")
    pump(root)
    assert dlg._folder_var.get() == str(tmp_path / "analysis-EGH-GRM")       # the suggestion follows the model
    assert enabled(dlg._match_chk)
    dlg._match_var.set(True)
    dlg._note_var.set("why")
    dlg._prepare_btn.invoke()
    pump(root)
    assert enabled(dlg._start_btn) and "SV 73.75" in dlg._preview_var.get()
    source, new, kwargs = library.calls[0]
    assert new == str(tmp_path / "analysis-EGH-GRM") and kwargs["model"] == "grm" and kwargs["match_curves"] is True
    assert kwargs["note"] == "why" and kwargs["method"] == "BH" and kwargs["seed"] == 'auto'

    dlg._start_btn.invoke()
    (plan, score, n_jobs, method), = started
    assert n_jobs == 4 and method == "BH" and plan.new_folder == new and score.sv == 73.75
    assert not dlg._dlg.winfo_exists()


def test_changing_a_field_asks_to_prepare_again(root, tmp_path, library):
    started = []
    dlg = _dialog(root, tmp_path, started)
    dlg._prepare_btn.invoke()
    pump(root)
    assert enabled(dlg._start_btn)
    dlg._method_var.set("DE")
    pump(root)
    assert not enabled(dlg._start_btn) and "prepare again" in dlg._status_var.get()
    dlg._start()
    assert started == []


def test_match_curves_is_offered_for_grm_and_lkm_only(root, tmp_path, library):
    dlg = _dialog(root, tmp_path, [])
    for label, expected in (("SDM", False), ("GRM", True), ("EDM", False), ("LKM", True), ("EGH", False)):
        dlg._model_var.set(label)
        pump(root, 0.05)
        assert enabled(dlg._match_chk) == expected, label
    dlg._model_var.set("GRM")
    dlg._match_var.set(True)
    dlg._model_var.set("SDM")
    pump(root, 0.05)
    assert dlg._match_var.get() is False                                       # it cannot stay ticked


def test_a_folder_that_holds_an_analysis_is_refused_before_anything_is_built(root, tmp_path, library):
    dlg = _dialog(root, tmp_path, [])
    taken = tmp_path / "taken"
    os.makedirs(taken / "optimized")
    dlg._folder_var.set(str(taken))
    dlg._prepare_btn.invoke()
    pump(root)
    assert "already holds an analysis" in dlg._status_var.get()
    assert library.calls == [] and not enabled(dlg._start_btn)


def test_the_dialog_is_shown_once(root, tmp_path, library):
    ctx = fork_dialog.ForkContext(str(tmp_path / "a"), object(), object(), {"model": "egh"})
    first = fork_dialog.show_fork_dialog(root, tk.StringVar(), ctx, lambda *a: None)
    second = fork_dialog.show_fork_dialog(root, tk.StringVar(), ctx, lambda *a: None, previous=first)
    assert second is first


# -- the run view ---------------------------------------------------------------------------------------------

def test_a_fork_passes_its_seed_to_the_run_and_a_plain_run_passes_nothing_extra():
    from molass_gui.rigorous_view import RigorousView
    plain = RigorousView(None, None, {'pipeline_recipe': {}}, "folder")
    assert plain._optimize_extras() == {}
    fork = RigorousView(None, None, {'pipeline_recipe': {}, 'num_jobs': 3,
                                     'optimize_extra': {'seed_params': [1.0], 'seed_source': 's'}}, "folder")
    assert fork._optimize_extras() == {'seed_params': [1.0], 'seed_source': 's'} and fork._num_jobs == 3
    fork._optimize_extras()['seed_params'] = None                      # a copy: the stored extras stay
    assert fork._optimize_extras()['seed_params'] == [1.0]
