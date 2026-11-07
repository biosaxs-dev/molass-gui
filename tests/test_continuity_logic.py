"""Continuity dialog (molass-gui#12): the Tk-free logic and a smoke test of the dialog."""
import numpy as np
import pytest

pytest.importorskip("molass.Continuity")     # needs a molass with Decomposition.get_continuity_report()
from molass.Continuity import compute_continuity_report
from molass_gui.continuity_logic import is_available, window_title, report_text, UNAVAILABLE_MESSAGE


def _report():
    rng = np.random.default_rng(0)
    frames = np.arange(120, dtype=float)
    rgs = np.repeat([60.0, 40.0, 25.0], 40) + 0.4*rng.standard_normal(120)
    return compute_continuity_report(frames, rgs, component_rgs=[60, 40, 25])


def test_is_available_checks_the_method():
    class Old:
        pass

    class New:
        def get_continuity_report(self, rgcurve=None):
            return None

    assert not is_available(Old())
    assert is_available(New())
    assert "get_continuity_report" in UNAVAILABLE_MESSAGE


def test_window_title_tells_the_stage():
    assert window_title(None) == "Continuity"
    assert window_title("Quick") == "Continuity \u2014 Quick"


def test_report_text_has_heading_and_verdict():
    report = _report()
    assert report_text(report).startswith("ContinuityReport: DISCRETE")
    text = report_text(report, "SAMPLE1 | GRM | BH")
    assert text.startswith("SAMPLE1 | GRM | BH\n\n") and "plateau excess" in text


def test_dialog_builds_and_closes():
    tk = pytest.importorskip("tkinter")
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("no display")
    root.withdraw()
    try:
        from molass_gui.continuity_dialog import ContinuityDialog
        dialog = ContinuityDialog(root, _report(), stage="Quick", heading="SAMPLE1 | GRM | BH")
        assert dialog._dlg.title() == "Continuity \u2014 Quick"
        dialog._dlg.destroy()
    finally:
        root.destroy()


def _tk_root():
    tk = pytest.importorskip("tkinter")
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("no display")
    root.withdraw()
    return tk, root


def _pump(root, done, seconds=20):
    import time
    end = time.time() + seconds
    while not done() and time.time() < end:
        root.update()
        time.sleep(0.05)
    return done()


def test_show_continuity_runs_in_the_background_and_restores_the_status():
    import time
    tk, root = _tk_root()
    try:
        from molass_gui.continuity_dialog import show_continuity

        class Decomp:
            def get_continuity_report(self, rgcurve=None):
                time.sleep(0.5)
                return _report()

        status = tk.StringVar(value="Ready")
        show_continuity(root, status, Decomp(), stage="Quick")
        assert "Computing continuity report" in status.get()        # returns at once, the window stays live
        tops = lambda: [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]
        assert _pump(root, lambda: len(tops()) == 1)
        assert tops()[0].title() == "Continuity \u2014 Quick" and status.get() == "Ready"
        tops()[0].destroy()
    finally:
        root.destroy()


def test_show_continuity_reports_a_failure_in_a_dialog():
    tk, root = _tk_root()
    try:
        from molass_gui.continuity_dialog import show_continuity

        class Decomp:
            def get_continuity_report(self, rgcurve=None):
                raise RuntimeError("no Rg curve")

        status = tk.StringVar(value="Ready")
        show_continuity(root, status, Decomp())
        tops = lambda: [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]
        assert _pump(root, lambda: len(tops()) == 1)
        assert tops()[0].title() == "Continuity report failed" and "no Rg curve" in status.get()
        tops()[0].destroy()
    finally:
        root.destroy()
