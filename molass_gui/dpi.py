"""High-DPI display support (Windows), kept in one place.

Without it Windows treats the process as DPI-unaware and bitmap-scales every window (blurry on a 4K screen at 150 %).
``enable()`` (before the first Tk window) makes the process system-DPI aware, so text and plots are drawn sharply.
``init(root)`` then fixes the *size* of the interface by one scale factor: 1.0 is the size of a 100 % display
(the default, compact), ``auto`` follows the system scaling (150 % -> 1.5), any number in between or above is allowed
(``--ui-scale``). The factor goes to Tk (font scaling), to matplotlib (``figure.dpi``) and to the sizes written as
``px(...)`` / ``geometry(...)``.
"""
import sys

DEFAULT_UI_SCALE = "1.0"
MIN_SCALE, MAX_SCALE = 0.5, 4.0
BASE_FIGURE_DPI = 100.0     # matplotlib's default, kept for savefig so that exported images do not change

_factor = 1.0
_system = 1.0       # the system scaling seen by ``init`` (before Tk's own scaling is changed)
_requested = DEFAULT_UI_SCALE


def parse_ui_scale(text):
    """``"auto"`` -> None (follow the system), ``"1.25"`` -> 1.25. Raises ValueError for anything else."""
    text = str(text).strip().lower()
    if text == "auto":
        return None
    value = float(text)
    if not MIN_SCALE <= value <= MAX_SCALE:
        raise ValueError(f"the UI scale must be 'auto' or between {MIN_SCALE} and {MAX_SCALE}")
    return value


def set_ui_scale(text):
    """The scale chosen at start-up (``--ui-scale``), used by ``init``."""
    global _requested
    parse_ui_scale(text)
    _requested = text


def enable():
    """Declare the process system-DPI aware. Must precede the first ``tk.Tk()``; harmless elsewhere or on failure."""
    if sys.platform != "win32":
        return
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)      # 1: system DPI aware (one factor for the session)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def init(root):
    """Decide the scale factor for this session and apply it to Tk and matplotlib. Returns the factor."""
    global _factor, _system
    system = _system = max(1.0, float(root.winfo_fpixels("1i")) / 96.0)
    chosen = parse_ui_scale(_requested)
    _factor = system if chosen is None else chosen
    # Tk sizes its fonts (given in points) by this value: 96 dpi / 72 points per inch at factor 1.0
    root.tk.call("tk", "scaling", 96.0 * _factor / 72.0)
    import matplotlib
    matplotlib.rcParams["figure.dpi"] = BASE_FIGURE_DPI * _factor
    matplotlib.rcParams["savefig.dpi"] = BASE_FIGURE_DPI
    return _factor


def factor():
    return _factor


def titlebar_width(root, title):
    # root.winfo_fpixels("1i") cannot be asked here: init() has already replaced Tk's scaling by the UI scale
    """Pixels a window needs for its whole *title* to show in the title bar.

    The title bar is drawn by Windows at the system DPI, independent of ``--ui-scale``, so a window sized by
    ``px(...)`` at factor 1.0 on a 150 % display is too narrow and the title is cut off ("Molass...").
    Counts the icon, the title in the caption font and the three caption buttons (all given for 96 dpi).
    """
    import tkinter.font as tkfont
    system = _system if sys.platform == "win32" else 1.0
    caption = tkfont.Font(root=root, family="Segoe UI", size=-int(round(12 * system)))
    try:
        text = caption.measure(title)
    finally:
        del caption
    return int(round((16 + 8 + 3 * 46 + 8) * system)) + text


def px(n):
    """A size given for 96 dpi, in pixels of this display."""
    return int(round(n * _factor))


def geometry(width, height):
    """A ``Tk.geometry`` size string for a window designed at 96 dpi."""
    return f"{px(width)}x{px(height)}"
