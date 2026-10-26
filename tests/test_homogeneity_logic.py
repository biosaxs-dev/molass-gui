"""Tk-free logic of the Homogeneity dialog."""
import pytest

pytest.importorskip("molass.Homogeneity.Report")     # needs a molass with SecSaxsData.homogeneity()
from molass_gui.homogeneity_logic import (default_proxy_names, normalize_proxy_name, preset_pairs,
                                          pairs_from_matrix, parse_cores, format_cores, PRESETS)

Q1, Q2 = 0.021, 0.063
NAMES = default_proxy_names(Q1, Q2, True)


def test_default_proxy_names():
    assert NAMES == ["I(0)", "I(0.021)", "I(0.063)", "A260", "A280", "A290", "A320"]
    assert default_proxy_names(Q1, Q2, False) == ["I(0)", "I(0.021)", "I(0.063)"]


def test_normalize_proxy_name():
    assert normalize_proxy_name(" i(0.03) ") == "I(0.03)"
    assert normalize_proxy_name("I(0)") == "I(0)"
    assert normalize_proxy_name("i( 0 )") == "I(0)"
    assert normalize_proxy_name("a250") == "A250"
    assert normalize_proxy_name("A 280.0") == "A280"
    for bad in ("B280", "I()", "A", "250", "I(x)"):
        with pytest.raises(ValueError):
            normalize_proxy_name(bad)


def test_presets():
    default = preset_pairs("Default", NAMES, Q1, Q2, True)
    assert default[:2] == [("I(0)", "I(0.021)"), ("I(0)", "A280")] and len(default) == 6
    assert preset_pairs("Classical only", NAMES, Q1, Q2, True) == [("I(0)", "I(0.021)"), ("I(0)", "A280")]
    assert preset_pairs("XR only", NAMES, Q1, Q2, True) == [("I(0)", "I(0.021)"), ("I(0)", "I(0.063)"),
                                                          ("I(0.021)", "I(0.063)")]
    assert preset_pairs("UV only", NAMES, Q1, Q2, True) == [("A260", "A280"), ("A280", "A290"), ("A320", "A280")]
    assert preset_pairs("XR / A280", NAMES, Q1, Q2, True) == [("I(0)", "A280"), ("I(0.021)", "A280"), ("I(0.063)", "A280")]
    assert len(preset_pairs("All pairs (one direction)", NAMES, Q1, Q2, True)) == 21
    assert set(PRESETS) >= {"Default", "Classical only"}
    with pytest.raises(ValueError):
        preset_pairs("nonsense", NAMES, Q1, Q2, True)


def test_presets_without_uv_and_with_missing_proxies():
    names = default_proxy_names(Q1, Q2, False)
    assert preset_pairs("Default", names, Q1, Q2, False) == [("I(0)", "I(0.021)"), ("I(0.021)", "I(0.063)")]
    assert preset_pairs("UV only", names, Q1, Q2, False) == []
    # a preset never refers to a proxy that is not in the matrix
    assert preset_pairs("Default", ["I(0)", "I(0.021)"], Q1, Q2, True) == [("I(0)", "I(0.021)")]


def test_pairs_from_matrix():
    state = {("a", "b"): True, ("b", "a"): False, ("a", "a"): True, ("b", "c"): True}
    assert pairs_from_matrix(state) == [("a", "b"), ("b", "c")]


def test_parse_and_format_cores():
    assert parse_cores("77-113, 145-170") == [(77, 113), (145, 170)]
    assert parse_cores("10:20;30 - 40") == [(10, 20), (30, 40)]
    assert format_cores([(77, 113), (145, 170)]) == "77-113, 145-170"
    for bad in ("", "5", "20-10", "a-b"):
        with pytest.raises(ValueError):
            parse_cores(bad)
