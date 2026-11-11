"""Tk-free logic of the Mass dialog (molass-gui#13, molass-library#381): availability, texts, rounding, table rows."""
import math

UNAVAILABLE_MESSAGE = ("The installed molass has no volume-of-correlation mass (molass-library#381). "
                       "Update molass to 1.2.4 or later.")
BUSY_MESSAGE = "Computing masses\u2026"

# Shown with every mass, so that it is not read as an exact value (molass-library#381).
CAVEAT = ("Caveat: protein calibration (volume of correlation, Rambo and Tainer 2013), concentration-free. "
          "On 11 SASBDB proteins it gives 0.77-0.95 of the sequence mass; it is not for non-protein or strongly "
          "non-compact particles. For such species the mass curve follows Rg along the elution, so it cannot tell "
          "a conformational continuum from species of different size. Values are rounded to two figures.")


def is_available():
    """Whether the installed molass can compute the volume-of-correlation mass."""
    try:
        from molass.SAXS.VolumeMass import volume_mass_curve  # noqa: F401
        from molass.LowRank.Component import XrComponent
    except ImportError:
        return False
    return callable(getattr(XrComponent, "get_volume_mass", None))


def window_title(stage):
    return f"Mass \u2014 {stage}" if stage else "Mass"


def round_figures(value, figures=2):
    """``449.6 -> 450``, ``35.7 -> 36``, ``1.234 -> 1.2``; NaN stays NaN."""
    if value is None or not math.isfinite(value) or value == 0:
        return value
    return round(value, figures - 1 - int(math.floor(math.log10(abs(value)))))


def fmt_mass(kda):
    """The mass in kDa to two significant figures, ``"n/a"`` when it could not be computed."""
    kda = round_figures(kda)
    if kda is None or not math.isfinite(kda):
        return "n/a"
    return f"{kda:g}"


def component_rows(components):
    """``[(component number, Rg text, mass text, note), ...]`` of the XR components.

    The note says why the mass is missing (too few points below the q cut, no valid Rg, ...)."""
    rows = []
    for i, comp in enumerate(components, start=1):
        try:
            vm = comp.get_volume_mass()
        except Exception as exc:
            rows.append((i, "n/a", "n/a", str(exc) or type(exc).__name__))
            continue
        rg = vm.rg
        rg_text = f"{rg:.1f}" if rg is not None and math.isfinite(rg) else "n/a"
        rows.append((i, rg_text, fmt_mass(vm.mass), "" if vm else (vm.reason or "")))
    return rows


def compute_mass(decomp, rgcurve=None):
    """``(rows, curve, curve_error)`` for *decomp*: the component rows and the per-frame ``VolumeMassCurve``.

    The curve uses the view's Rg curve (a curve restored from disk has no I(0): ``ensure_i0_rgcurve`` fits
    the frames again, about 30 s). If it could not be computed, ``curve`` is None and ``curve_error`` says why;
    the table is still returned."""
    rows = component_rows(decomp.get_xr_components())
    try:
        from molass.Homogeneity import ensure_i0_rgcurve
        from molass.SAXS.VolumeMass import volume_mass_curve
        ssd = decomp.ssd
        curve = volume_mass_curve(ssd.xr, ensure_i0_rgcurve(ssd, rgcurve))
    except Exception as exc:
        return rows, None, str(exc) or type(exc).__name__
    if len(curve.frames) == 0:
        return rows, None, "no frame has a reliable Guinier fit with enough intensity"
    return rows, curve, None
