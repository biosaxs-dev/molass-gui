"""Shared session state threaded through every phase view.

Lets any view export a notebook reproducing the exact pipeline run in the GUI
so far (see notebook_export.py) -- the bridge between molass-gui's simple
wizard and full notebook flexibility.
"""
import os


SAMPLE_PACKAGES = (
    ("molass_data", lambda name: name.startswith("SAMPLE")),
    ("molass_benchmarks", lambda name: name.isupper()),
)


def iter_samples():
    """Yield ``(package, name, path)`` of the bundled sample datasets: ``SAMPLE*`` of ``molass_data`` and the
    upper-case attributes of ``molass_benchmarks`` (e.g. ``PROTEINS5``). Packages that are not installed are
    skipped (both are optional convenience dependencies)."""
    import importlib
    for package, selects in SAMPLE_PACKAGES:
        try:
            module = importlib.import_module(package)
        except ImportError:
            continue
        for name in dir(module):
            path = getattr(module, name)
            if selects(name) and isinstance(path, str):
                yield package, name, path


def to_sample_ref(local_path):
    """Return ``(package, name)`` (e.g. ``('molass_data', 'SAMPLE1')``) of the bundled dataset that lives at
    local_path, else None (also when the packages aren't installed).

    The exported notebook then loads it as ``molass_data.SAMPLE1`` instead of baking in this machine's absolute
    site-packages path, which would break on any other machine or environment.
    """
    target = os.path.normcase(os.path.realpath(local_path))
    for package, name, path in iter_samples():
        if os.path.normcase(os.path.realpath(path)) == target:
            return package, name
    return None


def to_sample_name(local_path):
    """Return the attribute name (e.g. ``'SAMPLE1'``, ``'PROTEINS5'``) of the bundled dataset that lives at
    local_path, else None. See :func:`to_sample_ref` for the package too."""
    ref = to_sample_ref(local_path)
    return None if ref is None else ref[1]


def sample_path(name):
    """Path of the bundled dataset with this attribute name, or None."""
    for package, sample, path in iter_samples():
        if sample == name:
            return path
    return None


def to_dropbox_path(local_path):
    """Return the Dropbox-API-relative path if local_path looks like a
    Dropbox-synced folder, else None.

    Heuristic (per Copilot/DESIGN_dropbox_integration.md): a path segment
    literally containing "dropbox" marks the folder as Dropbox-synced;
    everything after that segment is the Dropbox-API-relative path. Shared
    between app.py (load-time sync) and notebook_export.py (exported
    notebook must also resolve via Dropbox, not read the raw local path
    directly -- that would defeat the whole point of syncing).
    """
    parts = [p for p in local_path.replace("\\", "/").split("/") if p]
    for i, p in enumerate(parts):
        if "dropbox" in p.lower():
            return "/" + "/".join(parts[i + 1:])
    return None


class SessionContext:
    """Accumulates GUI choices as the session progresses.

    Views mutate the fields they're responsible for, then pass the same
    instance forward to the next view. No copying is needed: each phase
    strictly adds fields and never revisits an earlier one (no Back button).
    """

    def __init__(self, folder):
        self.folder = folder
        self.uv_pickat = None  # UV wavelength (nm) override from app.py's Load dialog; None = library default (280)
        self.small_angle_limit = None  # trimmed_copy(small_angle_limit=...) from the Load dialog's advanced choice; None = library default
        self.num_components = None
        self.proportions = None  # actual proportions list used (custom or auto), or None for default decomposition
        self.xr_peakpositions = None  # frames of the peaks the user chose (molass-gui#14), or None = library default
        self.proportions_source = None  # 'uv' if the "on UV" checkbox was checked, else None (library default 'xr')
        self.trust_proportions = True  # False only for the GUI's own low-confidence equal-split fallback
        self.constraint_weight = None  # LumpingConstraint weight override; None = library default (see molass-gui#3)
        self.model_info = None       # {'model', 'pore_dist', 'ln_pore_sigma'}
        self.method = None
        self.analysis_folder = None
        self.num_jobs = None  # successive reseeded jobs (molass-researcher experiment 36)
        self.xr_ranks = None  # set via QuickView's Ranks entry (Decomposition.update_xr_ranks)

    @property
    def sample_ref(self):
        """``(package, name)`` (e.g. ``('molass_data', 'SAMPLE1')``) if self.folder is a bundled sample
        dataset, else None. Takes precedence over dropbox_path in exports."""
        return to_sample_ref(self.folder)

    @property
    def sample_name(self):
        """Attribute name (e.g. 'SAMPLE1', 'PROTEINS5') if self.folder is a bundled sample dataset, else None."""
        ref = self.sample_ref
        return None if ref is None else ref[1]

    @property
    def dropbox_path(self):
        """Dropbox-API-relative path if self.folder is Dropbox-synced, else None.

        Gated behind feature_flags.DROPBOX_SUPPORT_ENABLED so an exported
        notebook never depends on Dropbox sync unless the GUI itself was run
        with --dropbox-support (keeps load-time and export-time behavior
        consistent -- see Copilot/DESIGN_dropbox_integration.md).
        """
        from molass_gui import feature_flags
        if not feature_flags.DROPBOX_SUPPORT_ENABLED:
            return None
        return to_dropbox_path(self.folder)

