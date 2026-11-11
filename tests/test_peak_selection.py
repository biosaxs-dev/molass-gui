"""molass-gui#14: the pure helpers of the Peak positions choice."""
import numpy as np
import pytest

from molass_gui.peak_selection import (parse_positions, format_positions, classify_peaks, default_selection,
                                       default_peak_positions, toggle_peak)


def test_parse_and_format_positions():
    assert parse_positions("") == []
    assert parse_positions(" 648, 561 ;760 ") == [561, 648, 760]
    assert parse_positions("561.4, 648") == [561, 648]
    assert format_positions([561, 648, 760]) == "561, 648, 760"


@pytest.mark.parametrize("text, message", [("561, abc", "frame numbers"), ("561, 561", "different"),
                                           ("5000", "outside"), ("-3", "outside")])
def test_parse_positions_errors(text, message):
    with pytest.raises(ValueError, match=message):
        parse_positions(text, frames=(0, 1304))


def test_classify_and_default_selection_on_the_proteins5_numbers():
    detected = [500, 562, 648, 758, 827, 871, 1103]
    flags = [False, True, True, True, True, True, False]    # molass's get_confirmed_peaks().confirmed
    candidates = classify_peaks(detected, flags)
    assert [d for d, ok in candidates if ok] == [562, 648, 758, 827, 871]
    assert [d for d, ok in candidates if not ok] == [500, 1103]
    assert default_selection(candidates) == [562, 648, 758, 827, 871]
    assert default_selection(classify_peaks(detected, None)) == detected     # no confirmation: all detected peaks
    assert default_selection(classify_peaks(detected, [False]*7)) == detected   # nothing confirmed: all detected peaks


def test_default_peak_positions_only_when_the_library_leaves_peaks_out():
    detected = {'num_components': 7, 'xr_peakpositions': np.array([500, 562, 648, 758, 827, 871, 1103])}
    confirmed = {'num_components': 5, 'xr_peakpositions': np.array([562, 648, 758, 827, 871])}
    assert default_peak_positions(detected, confirmed) == [562, 648, 758, 827, 871]
    assert default_peak_positions(detected, detected) == []                  # the mapping did not rule peaks out
    proportions = {'num_components': 3, 'proportions': [1, 1, 1]}
    assert default_peak_positions(proportions, proportions) == []           # overlapping peaks: the fallback stays


def test_toggle_peak_adds_the_local_maximum_and_removes_a_chosen_peak():
    x = np.arange(200)
    y = np.exp(-0.5*((x - 100)/5.0)**2) + 0.5*np.exp(-0.5*((x - 150)/5.0)**2)
    added = toggle_peak([], 96, x, y)                       # near the first peak: snaps to its top
    assert added == [100]
    both = toggle_peak(added, 147, x, y)
    assert both == [100, 150]
    assert toggle_peak(both, 103, x, y) == [150]            # within 8 frames of a chosen peak: removed
    assert toggle_peak(both, 1000, x, y) == both            # no curve point near the click: nothing changes
    assert toggle_peak([], 96, x, y, candidates=[98]) == [98]   # a detected peak nearby wins over the local maximum
