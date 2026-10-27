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


def window_title(stage):
    """Title of the dialog window; the stage (Quick / Upgraded -- <model> / Rigorous) tells the figures apart."""
    return f"Homogeneity \u2014 {stage}" if stage else "Homogeneity"


def figure_title(heading, kind):
    """Suptitle of the figure: the ``dataset | model | method`` heading of the decomposition (the same line
    as the Plot Components figure) and which UV->XR mapping was used ('estimated' or 'optimized')."""
    return f"{heading} | mapping: {kind}" if heading else None


def optimized_mapping_of(decomp):
    """The UV->XR mapping the UV curves of *decomp* use when it differs from the estimated mapping of
    its data (a rigorous result, or a decomposition whose UV curves were optimized), else ``None``."""
    ssd = decomp.ssd
    if ssd.uv is None:
        return None
    mapping = decomp.get_uv_mapping()
    estimated = ssd.get_mapping()
    if mapping is None or estimated is None:
        return None
    a, b = tuple(mapping), tuple(estimated)
    if abs(a[0] - b[0]) <= 1e-9 * max(1.0, abs(b[0])) and abs(a[1] - b[1]) <= 1e-9 * max(1.0, abs(b[1])):
        return None
    return mapping
