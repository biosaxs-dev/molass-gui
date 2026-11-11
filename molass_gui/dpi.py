"""High-DPI display support (Windows), kept in one place.

Without it Windows treats the process as DPI-unaware and bitmap-scales every window (blurry on a 4K screen at 150 %).
``enable()`` (before the first Tk window) makes the process system-DPI aware; Tk then scales its fonts by itself, and
``init(root)`` carries the same factor to what is fixed in pixels: matplotlib figures (``figure.dpi``) and the sizes
written as ``px(...)`` / ``geometry(...)``. At 100 % everything is as before.
"""
import sys

_factor = 1.0
BASE_FIGURE_DPI = 100.0     # matplotlib's default, kept for savefig so that exported images do not change


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
    """Read the scale factor from the Tk root (pixels per inch / 96) and apply it to matplotlib. Returns the factor."""
    global _factor
    _factor = max(1.0, float(root.winfo_fpixels("1i")) / 96.0)
    if _factor != 1.0:
        import matplotlib
        matplotlib.rcParams["figure.dpi"] = BASE_FIGURE_DPI * _factor
        matplotlib.rcParams["savefig.dpi"] = BASE_FIGURE_DPI
    return _factor


def factor():
    return _factor


def px(n):
    """A size given for 96 dpi, in pixels of this display."""
    return int(round(n * _factor))


def geometry(width, height):
    """A ``Tk.geometry`` size string for a window designed at 96 dpi."""
    return f"{px(width)}x{px(height)}"
