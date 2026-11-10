"""molass-gui#14: the pure helpers of the Peak positions choice."""
import numpy as np
import pytest

from molass_gui.peak_selection import (parse_positions, format_positions, classify_peaks, default_selection,
                                       toggle_peak)


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
    mapping_peaks = [561, 648, 760, 825, 878]
    classified = classify_peaks(detected, mapping_peaks)
    assert [d for d, ok in classified if ok] == [562, 648, 758, 827, 871]
    assert [d for d, ok in classified if not ok] == [500, 1103]
    assert default_selection(detected, mapping_peaks) == [562, 648, 758, 827, 871]
    assert default_selection(detected, None) == sorted(detected)            # no mapping: all detected peaks
    assert default_selection(detected, [9999]) == sorted(detected)          # nothing confirmed: all detected peaks


def test_toggle_peak_adds_the_local_maximum_and_removes_a_chosen_peak():
    x = np.arange(200)
    y = np.exp(-0.5*((x - 100)/5.0)**2) + 0.5*np.exp(-0.5*((x - 150)/5.0)**2)
    added = toggle_peak([], 96, x, y)                       # near the first peak: snaps to its top
    assert added == [100]
    both = toggle_peak(added, 147, x, y)
    assert both == [100, 150]
    assert toggle_peak(both, 103, x, y) == [150]            # within 8 frames of a chosen peak: removed
    assert toggle_peak(both, 1000, x, y) == both            # no curve point near the click: nothing changes
