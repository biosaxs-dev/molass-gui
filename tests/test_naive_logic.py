"""molass-gui#16: the decisions of Decompose, with no Tk and no data."""
import pytest

from molass_gui.naive_logic import choose_decomposition, FALLBACK_LUMPING_WEIGHT

FRAMES = (0, 1304)


def choose(proportions="", positions="", nc=3, auto=None, **kwargs):
    return choose_decomposition(proportions, positions, nc, {"num_components": 3} if auto is None else auto,
                                frames=FRAMES, **kwargs)


def test_default_is_the_greedy_recognition_with_the_default_constraint():
    c = choose()
    assert c.quick_kwargs() == {"num_components": 3}
    assert c.trust_proportions and c.constraint_weight is None and c.used_message() == ""


def test_more_components_than_detected_falls_back_to_an_untrusted_equal_split():
    c = choose(nc=3, auto={"num_components": 2})
    assert c.quick_kwargs() == {"num_components": 3, "proportions": [1, 1, 1]}
    assert not c.trust_proportions and c.constraint_weight == FALLBACK_LUMPING_WEIGHT
    # the library's own recommendation of proportions (highly overlapping peaks) counts as well
    assert not choose(nc=2, auto={"num_components": 2, "proportions": [1, 1]}).trust_proportions


def test_typed_proportions_win_over_components_and_are_trusted():
    c = choose(proportions="1, 2", nc=5, auto={"num_components": 2}, on_uv=True)
    assert c.quick_kwargs() == {"num_components": 2, "proportions": [1.0, 2.0], "proportions_source": "uv"}
    assert c.trust_proportions and c.constraint_weight is None
    assert "proportions_source" not in choose(proportions="1, 2", on_uv=False).quick_kwargs()


def test_peak_positions_are_trusted_and_set_the_number_of_components():
    c = choose(positions="648, 561, 760", nc=7, auto={"num_components": 7, "xr_peakpositions": [1, 2]})
    assert c.quick_kwargs() == {"num_components": 3, "xr_peakpositions": [561, 648, 760]}
    assert c.xr_peakpositions == [561, 648, 760] and c.proportions is None
    assert c.trust_proportions and c.constraint_weight is None
    assert c.used_message() == "Used peak positions 561, 648, 760"


@pytest.mark.parametrize("kwargs, message", [
    (dict(proportions="1, x"), "comma-separated numbers"),
    (dict(positions="561, abc"), "frame numbers"),
    (dict(positions="5000"), "outside the frames"),
    (dict(proportions="1, 1", positions="561, 648"), "not both"),
])
def test_unusable_input_raises_a_message_for_the_status_line(kwargs, message):
    with pytest.raises(ValueError, match=message):
        choose(**kwargs)
