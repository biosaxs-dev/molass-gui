"""Tk-free logic of the Continuity dialog (molass-gui#12): window title, report text, availability check."""

UNAVAILABLE_MESSAGE = ("The installed molass has no Decomposition.get_continuity_report() "
                       "(molass-library#370). Update molass to a release that includes it.")
BUSY_MESSAGE = "Computing continuity report\u2026"


def is_available(decomp):
    """Whether the installed molass can make the continuity report of *decomp*."""
    return callable(getattr(decomp, "get_continuity_report", None))


def window_title(stage):
    """Title of the dialog window; the stage (Quick / Upgraded -- <model> / Rigorous) tells the figures apart."""
    return f"Continuity \u2014 {stage}" if stage else "Continuity"


def report_text(report, heading=None):
    """Text of the dialog: the ``dataset | model | method`` heading (if any) and the printed report."""
    return f"{heading}\n\n{report}" if heading else str(report)
