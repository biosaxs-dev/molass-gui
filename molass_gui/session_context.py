"""Shared session state threaded through every phase view.

Lets any view export a notebook reproducing the exact pipeline run in the GUI
so far (see notebook_export.py) -- the bridge between molass-gui's simple
wizard and full notebook flexibility.
"""


class SessionContext:
    """Accumulates GUI choices as the session progresses.

    Views mutate the fields they're responsible for, then pass the same
    instance forward to the next view. No copying is needed: each phase
    strictly adds fields and never revisits an earlier one (no Back button).
    """

    def __init__(self, folder):
        self.folder = folder
        self.num_components = None
        self.model_info = None       # {'model', 'pore_dist', 'ln_pore_sigma'}
        self.method = None
        self.analysis_folder = None
