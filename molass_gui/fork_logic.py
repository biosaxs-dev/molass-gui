"""What the "Continue as new analysis..." dialog decides, without any Tk (molass-library#396, molass-gui).

A fork starts a new analysis folder from the best result of an existing one, under the same elution model or
another (molass.fork_analysis). The dialog collects the model, whether to start near the current curves, the new
folder, a note, the method and the number of jobs; this module holds the rules for those fields.
"""
import os

# the models a fork can change to (what upgrade() builds); the quick decomposition is always EGH
UPGRADE_MODELS = ('sdm', 'edm', 'lkm', 'grm')
# the models `match_curves` is available for (molass.SEC.Models.MatchCurves)
MATCH_MODELS = ('grm', 'lkm')
METHODS = ('BH', 'DE')


def model_choices(source_model):
    """Model keys the dialog offers: the model of the source first (a fork under the same model), then the
    others a fork can change to."""
    source = str(source_model or 'egh').lower()
    return [source] + [m for m in UPGRADE_MODELS if m != source]


def match_available(source_model, target_model):
    """Whether "start near the current curves" applies: a model change to GRM or LKM."""
    return str(target_model).lower() != str(source_model).lower() and str(target_model).lower() in MATCH_MODELS


def default_new_folder(source_folder, target_model, source_model=None):
    """A free folder name next to the source: ``<source>-GRM`` for a model change, ``<source>-fork`` for the same
    model, numbered (``-2``, ``-3``, ...) while the name is taken."""
    source_folder = os.path.normpath(source_folder)
    parent, name = os.path.split(source_folder)
    same = source_model is not None and str(target_model).lower() == str(source_model).lower()
    base = f"{name}-fork" if same else f"{name}-{str(target_model).upper()}"
    candidate, n = base, 1
    while os.path.exists(os.path.join(parent, candidate)):
        n += 1
        candidate = f"{base}-{n}"
    return os.path.join(parent, candidate)


def check_new_folder(path, source_folder=None):
    """``None`` if ``path`` can be the folder of a new analysis, else the reason why not (one sentence)."""
    path = (path or "").strip()
    if not path:
        return "Give the folder of the new analysis."
    path = os.path.abspath(path)
    if source_folder is not None and os.path.normcase(path) == os.path.normcase(os.path.abspath(source_folder)):
        return "That is the folder of this analysis: Resume continues it, a new analysis needs another folder."
    if os.path.isfile(path):
        return "That path is a file."
    if os.path.isdir(os.path.join(path, "optimized")):
        return "That folder already holds an analysis: choose another folder."
    parent = os.path.dirname(path)
    if not os.path.isdir(parent):
        return f"The folder {parent} does not exist."
    return None


def check_fields(source_model, target_model, match_curves, new_folder, source_folder=None):
    """The first problem with the dialog's fields (a sentence), or ``None``."""
    target = str(target_model).lower()
    if target != str(source_model).lower() and target not in UPGRADE_MODELS:
        return f"A new analysis cannot change the model to {target.upper()}."
    if match_curves and not match_available(source_model, target):
        return "Starting near the current curves needs a change to GRM or LKM."
    return check_new_folder(new_folder, source_folder)


def summary_lines(plan, score, source_fv=None, source_sv=None):
    """Text for the preview: what job 000 of the new analysis starts from."""
    lines = []
    if plan.model != plan.source_model:
        lines.append(f"Model: {plan.source_model.upper()} \u2192 {plan.model.upper()}")
    else:
        lines.append(f"Model: {plan.model.upper()} (unchanged)")
    lines.append("Starts from: " + (plan.seeded_from or "the estimate of the decomposition"))
    info = getattr(plan.decomposition, 'match_curves_info', None)
    if info:
        lines.append("Curves matched: error %.3g \u2192 %.3g" % (info['start_error'], info['error'])
                     + ("" if info['improved'] else " (no improvement: the estimate is kept)"))
    lines.append("Start of job 000: SV %.2f (fv %.4f)" % (score.sv, score.fv))
    if source_sv is not None and source_fv is not None:
        lines.append("Best of this analysis: SV %.2f (fv %.4f)" % (source_sv, source_fv))
    lines.append(f"Method {plan.recipe.get('method', 'bh').upper()}, folder {plan.new_folder}")
    return lines


def optimize_extras(plan):
    """What the live run view passes on to ``optimize_rigorously`` besides its own arguments: the seed and what
    the plan fixed (the function code of the new model, frozen components, the note)."""
    keep = ('seed_params', 'seed_source', 'note', 'function_code', 'frozen_components', 'frozen_param_groups')
    return {key: plan.kwargs[key] for key in keep if plan.kwargs.get(key) is not None}
