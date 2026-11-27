"""What the GUI says about the rank-2 (interparticle) correction (molass-gui#26, #25), from ``decomposition.rank2_report()``.

Tk-free. The summary leads with the impact (how much the correction changes the Rg), then says how many checks were flagged; the notices carry the
findings in plain language (what it means, what it affects, what to check) with the library's own text kept under it. A finding is not a risk level:
the thresholds behind it are provisional (molass-library#423). Everything degrades when the installed ``molass`` is older (no ``rank2_report``,
no ``impact``, no ``findings``).
"""
from molass_gui import notices


def _short(convention):
    return "adaptive fit" if convention.startswith("adaptive") else "from the lowest q" if convention.startswith("from lowest") else convention


def _rg_changes(entry):
    """``[(convention, uncorrected, corrected, change %)]`` from the impact of the report, or from the two Rg tables of an older report."""
    if entry.get("impact"):
        return [(g["convention"], g["uncorrected"], g["corrected"], g["change_pct"]) for g in entry["impact"]["rg"]]
    corrected, uncorrected = entry.get("rg_corrected") or {}, entry.get("rg_uncorrected") or {}
    return [(name, uncorrected[name]["Rg"], v["Rg"], (v["Rg"] / uncorrected[name]["Rg"] - 1) * 100)
            for name, v in corrected.items() if name in uncorrected and uncorrected[name]["Rg"]]


def _flagged(entry):
    return len(entry["findings"]) if "findings" in entry else len(entry.get("warnings") or [])


def fmt_rank2_summary(report):
    """One line for the status bar, e.g. ``Ranks = 2: Rg 35.2 -> 34.2 A (-2.8 %, adaptive fit); 30.3 -> 33.5 A (+10.4 %, from the lowest q) | 2 checks flagged``;
    empty without a rank-2 component or a report."""
    if not report:
        return ""
    parts = []
    many = len(report) > 1
    for k, entry in report.items():
        if entry.get("note"):                       # not corrected (no valid Rg seed)
            parts.append(f"{'component %d: ' % (k + 1) if many else ''}not corrected: {entry['note']}")
            continue
        changes = [f"{u:.1f} -> {c:.1f} A ({pct:+.1f} %, {_short(name)})" for name, u, c, pct in _rg_changes(entry) if all(v == v for v in (u, c, pct))]
        n = _flagged(entry)
        flagged = "no checks flagged" if n == 0 else f"{n} check{'s' if n != 1 else ''} flagged (see the notice)"
        head = f"component {k + 1}: " if many else ""
        parts.append(f"{head}Rg " + "; ".join(changes) + f" | {flagged}" if changes else f"{head}{flagged}")
    return "Ranks = 2: " + "  ||  ".join(parts)


def findings_of(report):
    """``[(component index, finding)]`` over the report; empty when the report has no ``findings`` (an older molass)."""
    return [(k, f) for k, entry in (report or {}).items() for f in entry.get("findings") or []]


def build_rank2_notices(caught, report=None):
    """The notices of applying Ranks: with the findings of the report, a heading and per finding the plain text, what it affects and what to check, the
    library's text under it; the other captured warnings follow. Without findings (an older molass) the generic notices of :func:`notices.rank2_notices`."""
    found = findings_of(report)
    if not found:
        return notices.rank2_notices(caught)
    many = len(report) > 1
    covered = [f.text for _, f in found]
    out = [f"{len(found)} check{'s' if len(found) != 1 else ''} of the interparticle (rank-2) correction flagged; Details says what each means and what to check "
           f"(not a risk level: the thresholds are provisional)."]
    for k, f in found:
        who = f"Component {k + 1}: " if many else ""
        out.append(f"{who}{f.plain}\nAffects: {f.region}.\nCheck: {f.check}\n(molass: {f.text})")
    out.extend(m for m in dict.fromkeys(caught) if m and not any(t in m for t in covered))
    return out
