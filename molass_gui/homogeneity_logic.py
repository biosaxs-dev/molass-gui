"""Tk-free logic of the Homogeneity dialog: proxy names, presets of ratio sets, core text."""
import re

PRESETS = ["Default", "Classical only", "XR only", "UV only", "XR / A280", "All pairs (one direction)"]

_Q = re.compile(r"^[Ii]\(\s*(\d*\.?\d+(?:[eE][-+]?\d+)?)\s*\)$")
_A = re.compile(r"^[Aa]\s*(\d+(?:\.\d+)?)$")


def default_proxy_names(q1, q2, has_uv):
    names = ["I(0)", f"I({q1:g})", f"I({q2:g})"]
    if has_uv:
        names += ["A260", "A280", "A290", "A320"]
    return names


def normalize_proxy_name(text):
    """Canonical proxy name for user text: ``i(0.03)`` -> ``I(0.03)``, ``a250`` -> ``A250``, ``i(0)`` -> ``I(0)``.
    Raises ValueError for anything else."""
    t = text.strip()
    m = _Q.match(t)
    if m:
        q = float(m.group(1))
        return "I(0)" if q == 0 else f"I({q:g})"
    m = _A.match(t)
    if m:
        return f"A{float(m.group(1)):g}"
    raise ValueError(f"{text!r} is not a proxy name; use I(0), I(<q in 1/A>) or A<wavelength in nm>")


def preset_pairs(preset, names, q1, q2, has_uv):
    """(numerator, denominator) pairs of a preset, restricted to the proxies in ``names``."""
    from molass.Homogeneity.Report import default_pairs
    i1, i2 = f"I({q1:g})", f"I({q2:g})"
    xr = [n for n in names if n.startswith("I(")]
    if preset == "Default":
        pairs = default_pairs(q1, q2, has_uv)
    elif preset == "Classical only":
        pairs = [("I(0)", i1)] + ([("I(0)", "A280")] if has_uv else [])
    elif preset == "XR only":
        pairs = [(a, b) for k, a in enumerate(xr) for b in xr[k + 1:]]
    elif preset == "UV only":
        pairs = [("A260", "A280"), ("A280", "A290"), ("A320", "A280")] if has_uv else []
    elif preset == "XR / A280":
        pairs = [(x, "A280") for x in xr] if has_uv else []
    elif preset == "All pairs (one direction)":
        pairs = [(a, b) for k, a in enumerate(names) for b in names[k + 1:]]
    else:
        raise ValueError(f"unknown preset {preset!r}")
    return [p for p in pairs if p[0] in names and p[1] in names]


def pairs_from_matrix(state):
    """``state`` maps (numerator, denominator) -> bool; returns the selected pairs in insertion order."""
    return [pair for pair, on in state.items() if on and pair[0] != pair[1]]


def parse_cores(text):
    """``"77-113, 145-170"`` -> ``[(77, 113), (145, 170)]``; raises ValueError on bad text."""
    cores = []
    for part in re.split(r"[,;]", text):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"^(\d+)\s*[-:]\s*(\d+)$", part)
        if not m or int(m.group(1)) >= int(m.group(2)):
            raise ValueError(f"cannot read {part!r}; write first-last frames, e.g. 77-113, 145-170")
        cores.append((int(m.group(1)), int(m.group(2))))
    if not cores:
        raise ValueError("no cores given")
    return cores


def format_cores(cores):
    return ", ".join(f"{a}-{b}" for a, b in cores)
