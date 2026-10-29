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


def fmt_fronting(decomposition):
    """Which components may have a fronting peak in the rigorous stage (molass-library#350), one short text.

    Empty with a molass that does not know the policy, and for models that cannot front (SDM, LKM, GRM).
    """
    try:
        from molass.Rigorous.FrontingPolicy import describe, resolve_fronting
        flags = resolve_fronting(decomposition, None)
    except Exception:
        return ""
    if flags is None:
        return ""
    return "Fronting allowed: " + describe(flags)


def fmt_interparticle_hint(recommended_options):
    """Hint for the rank-2 (interparticle) case from ``recommend_decomposition_options()``; empty when not suspected."""
    ranks = (recommended_options or {}).get("ranks")
    if ranks and 2 in ranks:
        return ("Interparticle effect suspected (suppressed low-q intensity): "
                "consider Ranks = 2 in the next view")
    return ""
