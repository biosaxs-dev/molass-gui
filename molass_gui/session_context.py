"""Shared session state threaded through every phase view.

Lets any view export a notebook reproducing the exact pipeline run in the GUI
so far (see notebook_export.py) -- the bridge between molass-gui's simple
wizard and full notebook flexibility.
"""


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
        self.num_components = None
        self.proportions = None  # actual proportions list used (custom or auto), or None for default decomposition
        self.trust_proportions = True  # False only for the GUI's own low-confidence equal-split fallback
        self.model_info = None       # {'model', 'pore_dist', 'ln_pore_sigma'}
        self.method = None
        self.analysis_folder = None
        self.num_jobs = None  # successive reseeded jobs (molass-researcher experiment 36)

    @property
    def dropbox_path(self):
        """Dropbox-API-relative path if self.folder is Dropbox-synced, else None."""
        return to_dropbox_path(self.folder)

