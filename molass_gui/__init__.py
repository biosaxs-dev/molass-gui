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
