"""What the GUI shows about the angular range and the interparticle test (molass-library#342).

Pure helpers, no Tk, so they can be tested without a display.
"""

# (label shown, value for trimmed_copy(small_angle_limit=...)); None = the library default
SMALL_ANGLE_LIMITS = (
    ("Default", None),
    ("Extended Guinier limit", "extended"),
    ("Guinier start", "guinier"),
    ("All measured q", "none"),
)


def small_angle_limit_from_label(label):
    for text, value in SMALL_ANGLE_LIMITS:
        if text == label:
            return value
    return None


def trim_kwargs(small_angle_limit):
    """Keyword arguments of ``trimmed_copy`` for the chosen limit (none for the library default)."""
    return {} if small_angle_limit is None else {"small_angle_limit": small_angle_limit}


def fmt_qrange(ssd, trimmed):
    """One line telling which angular range the trimming kept; empty when it cannot be told."""
    try:
        import numpy as np
        raw_q = np.asarray(ssd.xr.qv)
        q = np.asarray(trimmed.xr.qv)
        text = f"q: {q[0]:.4f} \u2013 {q[-1]:.4f} \u00c5\u207b\u00b9"
        cut = int(np.argmin(np.abs(raw_q - q[0])))
        if cut:
            text += f"  ({cut} lowest-q points cut)"
        else:
            text += "  (all low-q points kept)"
        return text
    except Exception:
        return ""


def fmt_fronting(decomposition, show_b=False):
    """Which components may have a fronting peak in the rigorous stage (molass-library#350), one short text.

    Empty with a molass that does not know the policy, and for models that cannot front (SDM, LKM, GRM).
    With ``show_b``, an EDM decomposition whose non-fronting components all have b = 0 (the quick-stage
    default of molass-library#349) says so; read from the fitted parameters, not assumed.
    """
    try:
        from molass.Rigorous.FrontingPolicy import describe, resolve_fronting
        flags = resolve_fronting(decomposition, None)
    except Exception:
        return ""
    if flags is None:
        return ""
    text = "Fronting allowed: " + describe(flags)
    if show_b and _non_fronting_b_is_zero(decomposition, flags):
        text += "; b = 0 for the others" if any(flags) else "; b = 0"
    return text


def _non_fronting_b_is_zero(decomposition, flags):
    try:
        curves = decomposition.xr_ccurves
        if curves[0].model != 'edm':
            return False
        b = [float(cc.get_params()[3]) for cc, may_front in zip(curves, flags) if not may_front]
    except Exception:
        return False
    return bool(b) and all(abs(v) < 1e-9 for v in b)


def fmt_interparticle_hint(recommended_options):
    """Hint for the rank-2 (interparticle) case from ``recommend_decomposition_options()``; empty when not suspected."""
    ranks = (recommended_options or {}).get("ranks")
    if ranks and 2 in ranks:
        return ("Interparticle effect suspected (suppressed low-q intensity): "
                "consider Ranks = 2 in the next view")
    return ""
