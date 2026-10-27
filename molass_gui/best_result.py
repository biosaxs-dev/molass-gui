"""
    The best completed rigorous result of an analysis folder, for the dialogs that show or reuse it.

    One place for the logic that was copied into the Plot Components, Kratky Shape Match, Homogeneity
    and DENSS dialogs (molass-library#336): the *best* job (lowest objective value), not the latest
    one, with ``fv`` / ``sv`` attached, and the "no result yet" message.
"""
from tkinter import messagebox


def _load_best_fallback(decomp, analysis_folder, rgcurve=None, xr_ranks=None):
    # molass without load_best_rigorous_result() (before the release containing #336); drop once
    # molass-gui requires that release
    from molass.Rigorous.CurrentStateUtils import load_rigorous_result, list_rigorous_jobs, fv_to_sv
    jobs = list_rigorous_jobs(analysis_folder)
    if not jobs:
        raise FileNotFoundError("No completed job found")
    best = min(jobs, key=lambda j: j.best_fv)
    result = load_rigorous_result(decomp, analysis_folder, jobid=best.id, rgcurve=rgcurve, xr_ranks=xr_ranks)
    result.fv = best.best_fv
    result.sv = float(fv_to_sv(best.best_fv))
    return result


def load_best_result(win, decomp, analysis_folder, rgcurve=None, xr_ranks=None):
    """The best result in *analysis_folder* (``result.fv`` / ``result.sv`` attached), or ``None``
    after telling the user that the optimization has not produced a result yet.

    Parameters
    ----------
    win : tk widget
        Parent of the "No results yet" message.
    decomp : Decomposition
        The initial (pre-rigorous) decomposition the run started from.
    analysis_folder : str
    rgcurve : RgCurve, optional
        Pre-computed Rg curve to avoid redundant Guinier fitting.
    xr_ranks : list of int, optional
        Per-component rank override (see ``load_rigorous_result``).
    """
    try:
        from molass.Rigorous.CurrentStateUtils import load_best_rigorous_result, NoCompletedJobError
    except ImportError:
        load_best_rigorous_result, NoCompletedJobError = _load_best_fallback, FileNotFoundError
    try:
        return load_best_rigorous_result(decomp, analysis_folder, rgcurve=rgcurve, xr_ranks=xr_ranks)
    except NoCompletedJobError:
        # e.g. clicked right after launch: callback.txt only has the init-params entry, no search
        # step has completed yet -- not an error.
        messagebox.showinfo(
            "No results yet",
            "The optimization hasn't produced its first result yet.\n"
            "Try again in a moment.",
            parent=win,
        )
        return None
