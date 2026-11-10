"""Pure helpers of the "Peak positions" choice in NaiveView (molass-gui#14): parsing and formatting the
frame list, telling confirmed peaks from unconfirmed ones, and toggling a peak by a click. No Tk here,
so that it can be tested."""
import numpy as np

SNAP_FRAMES = 8          # a click this close (in frames) to a chosen peak removes it; otherwise it snaps to the local maximum
CONFIRM_TOL_FRAMES = 10  # a detected peak counts as confirmed if the XR/UV mapping has a peak this close


def parse_positions(text, frames=None):
    """Frame numbers typed as ``"561, 648, 760"`` -> sorted list of ints.

    ``frames`` is an optional ``(first, last)`` range every position must lie in. Raises ``ValueError``
    with a message fit for the status line (empty text gives an empty list)."""
    values = []
    for part in text.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            values.append(int(round(float(part))))
        except ValueError:
            raise ValueError(f"peak positions must be frame numbers separated by commas (got {part!r})") from None
    if frames is not None:
        lo, hi = int(frames[0]), int(frames[1])
        bad = [v for v in values if not lo <= v <= hi]
        if bad:
            raise ValueError(f"peak position {bad[0]} is outside the frames {lo}-{hi}")
    if len(set(values)) != len(values):
        raise ValueError("peak positions must be different")
    return sorted(values)


def format_positions(positions):
    return ", ".join(str(int(p)) for p in positions)


def classify_peaks(detected, confirmed, tol=CONFIRM_TOL_FRAMES):
    """``[(frame, is_confirmed), ...]`` of the detected peaks, sorted; a detected peak is confirmed when one
    of ``confirmed`` (the XR peaks of the XR/UV mapping) lies within ``tol`` frames."""
    confirmed = [int(c) for c in (confirmed if confirmed is not None else [])]
    out = []
    for d in sorted(int(p) for p in detected):
        out.append((d, any(abs(d - c) <= tol for c in confirmed)))
    return out


def default_selection(detected, confirmed, tol=CONFIRM_TOL_FRAMES):
    """The peaks "Use detected peaks" fills in: the confirmed ones, or all detected ones when none is confirmed
    (no UV data, or no mapping)."""
    classified = classify_peaks(detected, confirmed, tol)
    sure = [d for d, ok in classified if ok]
    return sure if sure else [d for d, _ in classified]


def toggle_peak(selected, clicked, x, y, snap=SNAP_FRAMES, candidates=()):
    """The chosen peaks after a click at frame ``clicked`` on the curve ``(x, y)``: a click within ``snap`` frames
    of a chosen peak removes the nearest one; otherwise a detected peak (``candidates``) within ``snap`` frames is
    added as it is, else the local maximum of the curve within ``snap`` frames of the click. A click on a flat
    region without any curve point nearby changes nothing."""
    selected = sorted(int(s) for s in selected)
    near = [s for s in selected if abs(s - clicked) <= snap]
    if near:
        selected.remove(min(near, key=lambda s: abs(s - clicked)))
        return selected
    marks = [int(c) for c in candidates if abs(c - clicked) <= snap]
    if marks:
        peak = min(marks, key=lambda c: abs(c - clicked))
        return sorted(selected + [peak])
    x = np.asarray(x)
    y = np.asarray(y)
    window = np.where(np.abs(x - clicked) <= snap)[0]
    if len(window) == 0:
        return selected
    peak = int(x[window[np.argmax(y[window])]])
    if peak not in selected:
        selected.append(peak)
    return sorted(selected)
