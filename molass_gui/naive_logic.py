"""The decisions NaiveView makes before it calls the library, as pure functions (molass-gui#16): no Tk, no data,
so that they can be tested in milliseconds."""
from dataclasses import dataclass
from typing import Optional

from molass_gui.peak_selection import parse_positions

# LumpingConstraint's own default (0.2) is calibrated for confident,
# independently-detected peak positions. When the equal-split fallback fires,
# a component's "position" is just the centroid of an arbitrary equal-area
# cut (see molass-library/molass/Decompose/Proportional.py) -- not a real
# detection. This weight is loose enough to not penalize legitimate
# refinement near that unconfirmed default, while still blocking gross
# (500+ frame) drift/collapse. See molass-gui#3.
FALLBACK_LUMPING_WEIGHT = 0.01


@dataclass
class DecomposeChoice:
    """Which ``quick_decomposition`` call Decompose makes, and what the session context records of it."""
    num_components: int
    proportions: Optional[list] = None
    xr_peakpositions: Optional[list] = None
    proportions_source: Optional[str] = None
    trust_proportions: bool = True

    @property
    def constraint_weight(self):
        return None if self.trust_proportions else FALLBACK_LUMPING_WEIGHT

    def quick_kwargs(self):
        """Keyword arguments of ``corrected.quick_decomposition``."""
        kwargs = {"num_components": self.num_components}
        if self.proportions is not None:
            kwargs["proportions"] = self.proportions
            if self.proportions_source:
                kwargs["proportions_source"] = self.proportions_source
        elif self.xr_peakpositions:
            kwargs["xr_peakpositions"] = self.xr_peakpositions
        return kwargs

    def used_message(self):
        """The status line after a successful decomposition."""
        if self.proportions is not None:
            return "Used proportional decomposition"
        if self.xr_peakpositions:
            return "Used peak positions " + ", ".join(str(p) for p in self.xr_peakpositions)
        return ""


def parse_proportions(text):
    """``"1, 2, 1"`` -> ``[1.0, 2.0, 1.0]``; ``None`` for empty text. Raises ``ValueError`` fit for the status line."""
    text = text.strip()
    if not text:
        return None
    try:
        return [float(s) for s in text.split(",")]
    except ValueError:
        raise ValueError("proportions must be comma-separated numbers") from None


def choose_decomposition(proportions_text, positions_text, num_components, auto_opts, frames=None, on_uv=False):
    """Decide how Decompose calls the library from what the user typed and what the detection recommended.

    ``auto_opts`` is ``recommend_decomposition_options()`` (``{}`` when the detection failed), ``frames`` the
    ``(first, last)`` frame range the peak positions must lie in. Raises ``ValueError`` with a message fit for
    the status line when the input is unusable.
    """
    custom_proportions = parse_proportions(proportions_text)
    peak_positions = parse_positions(positions_text, frames)
    # Peak positions is an alternative to Proportions, not a complement: both fix where the
    # components sit, so giving both is ambiguous.
    if peak_positions and custom_proportions is not None:
        raise ValueError("give either Peak positions or Proportions, not both")

    # Components is kept in sync live by the view, but derive it here too so a mismatch can never
    # actually occur regardless of widget-event timing.
    if custom_proportions is not None:
        return DecomposeChoice(len(custom_proportions), proportions=custom_proportions,
                               proportions_source="uv" if on_uv else None)
    if peak_positions:
        # the user's own positions, not a patch: default constraint weight
        return DecomposeChoice(len(peak_positions), xr_peakpositions=peak_positions)

    # Highly-overlapping peaks (e.g. SAMPLE4) make the default greedy peak-recognition unstable;
    # recommend_decomposition_options() detects this via EGH peeling -- but only at the component count
    # IT finds on its own. Forcing more components than that (e.g. nc=3 when auto-detection only
    # distinguishes 2) is itself the unstable case -- SAMPLE4's 3rd component is invisible to
    # auto-detection but still needs proportional slicing, not the greedy default.
    auto_nc = auto_opts.get("num_components", num_components)
    needs_fallback = "proportions" in auto_opts or num_components > auto_nc
    if needs_fallback:
        # This equal split is a patch for the peeling algorithm's own shortfall, not a choice the user
        # made -- must not silently pose as a validated, precisely-known position. But that doesn't mean
        # no constraint should apply: loosen it instead of disabling it (molass-gui#3).
        return DecomposeChoice(num_components, proportions=[1] * num_components, trust_proportions=False)
    return DecomposeChoice(num_components)
