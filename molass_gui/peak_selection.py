"""Pure helpers of the "Peak positions" choice in NaiveView (molass-gui#14): parsing and formatting the
frame list, telling confirmed peaks from unconfirmed ones, and toggling a peak by a click. No Tk here,
so that it can be tested."""
import numpy as np

SNAP_FRAMES = 8          # a click this close (in frames) to a chosen peak removes it; otherwise it snaps to the local maximum


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


def classify_peaks(positions, confirmed):
    """``[(frame, is_confirmed), ...]`` of the detected peaks, sorted. ``confirmed`` are the flags of molass's
    ``corrected.get_confirmed_peaks()`` for ``positions``, or ``None`` when they are not available (every peak
    then counts as unconfirmed)."""
    flags = [False] * len(positions) if confirmed is None else [bool(c) for c in confirmed]
    return sorted((int(p), c) for p, c in zip(positions, flags))


def default_selection(candidates):
    """The peaks "Show confirmed peaks" fills in: the confirmed ones, or all detected ones when none is confirmed
    (no UV data, or no mapping)."""
    sure = [d for d, ok in candidates if ok]
    return sure if sure else [d for d, _ in candidates]


def default_peak_positions(auto_opts, confirmed_opts):
    """The peak positions Decompose starts with, or ``[]`` for the default decomposition.

    ``auto_opts`` is ``recommend_decomposition_options()`` and ``confirmed_opts`` the same with
    ``confirm_with_uv=True``: the latter has fewer peaks only when the XR/UV mapping rests on enough peaks to
    show that the others are spurious (PROTEINS5: 5 of 7). Otherwise the default stays as it is."""
    if 'xr_peakpositions' not in confirmed_opts or 'xr_peakpositions' not in auto_opts:
        return []
    chosen = sorted(int(p) for p in confirmed_opts['xr_peakpositions'])
    if len(chosen) >= len(auto_opts['xr_peakpositions']):
        return []
    return chosen


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
