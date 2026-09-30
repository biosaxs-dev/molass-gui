"""molass-gui — Tkinter GUI for Molass initial estimate workflow."""
import os


def get_version():
    """Return the molass_gui version -- from pyproject.toml in a dev checkout,
    else from importlib.metadata for an installed package (same convention as
    molass.get_version())."""
    pyproject_toml = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'pyproject.toml')
    if os.path.exists(pyproject_toml):
        import toml
        return toml.load(pyproject_toml)['project']['version']
    import importlib.metadata
    return importlib.metadata.version('molass_gui')


__version__ = get_version()


def context_path():
    """Return the absolute path to CONTEXT.md, the AI-assistant context file
    shipped inside this package. See :func:`molass.context_path` for the
    main (molass-library) context file this one supplements.
    """
    return os.path.join(os.path.dirname(__file__), "CONTEXT.md")


def print_context():
    """Print CONTEXT.md (see :func:`context_path`) to stdout."""
    with open(context_path(), encoding="utf-8") as fh:
        text = fh.read()
    try:
        print(text)
    except UnicodeEncodeError:
        # e.g. cp932 consoles on Japanese Windows can't encode en-dashes/arrows;
        # fall back to a safe, lossy print rather than crashing.
        import sys
        print(text.encode(sys.stdout.encoding or "ascii", errors="replace").decode(sys.stdout.encoding or "ascii"))
