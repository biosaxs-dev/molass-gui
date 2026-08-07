"""UpgradedView — Phase 4: upgraded plot_components + method/subprocess → RigorousView."""
import tkinter as tk
from tkinter import ttk

_METHOD_LABELS = ['BH', 'DE']


class UpgradedView:
    def __init__(self, decomp, trimmed, nc, model_info, parent=None):
        """
        Parameters
        ----------
        decomp : Decomposition
            Upgraded (or EGH) decomposition.
        trimmed : SecSaxsData
            Trimmed SSD for score().
        nc : int
            Number of components (for pipeline_recipe).
        model_info : dict
            Keys: model, pore_dist, ln_pore_sigma.
        parent : tk widget or None
        """
        self._decomp = decomp
        self._trimmed = trimmed
        self._nc = nc
        self._model_info = model_info
        self._parent = parent

    def show(self):
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

        win = tk.Toplevel(self._parent)
        model = self._model_info['model'].upper()
        win.title(f"Upgraded View \u2014 {model}")

        # Header: method + subprocess + Rigorous button
        hdr = ttk.Frame(win, padding=(8, 4))
        hdr.pack(fill=tk.X)

        ttk.Label(hdr, text="Method:").pack(side=tk.LEFT)
        self._method_var = tk.StringVar(value='BH')
        ttk.Combobox(hdr, textvariable=self._method_var, values=_METHOD_LABELS,
                     state='readonly', width=8).pack(side=tk.LEFT, padx=4)

        self._subprocess_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(hdr, text="Use subprocess",
                        variable=self._subprocess_var).pack(side=tk.LEFT, padx=12)

        self._rig_btn = ttk.Button(hdr, text="Rigorous Optimization\u2026",
                                   command=self._proceed_rigorous)
        self._rig_btn.pack(side=tk.RIGHT, padx=8)

        # Show plot_components for the current model
        result = self._decomp.plot_components()
        canvas = FigureCanvasTkAgg(result.fig, master=win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        NavigationToolbar2Tk(canvas, win).update()
        self._win = win

    def _proceed_rigorous(self):
        from tkinter import filedialog
        folder = filedialog.askdirectory(
            title="Select output folder for optimization results",
            parent=self._win)
        if not folder:
            return

        model_key     = self._model_info['model']
        pore_dist     = self._model_info['pore_dist']
        ln_pore_sigma = self._model_info['ln_pore_sigma']
        method        = self._method_var.get().lower()
        use_subprocess = self._subprocess_var.get()

        pipeline_recipe = {
            'num_components': self._nc,
            'model': model_key,
            'method': method,
            'decomp_params': {},
            'trim_params': {},
            'baseline_params': {},
        }
        if pore_dist is not None:
            pipeline_recipe['pore_dist'] = pore_dist
        if ln_pore_sigma is not None:
            pipeline_recipe['ln_pore_sigma'] = ln_pore_sigma

        est_kwargs = {
            'use_subprocess': use_subprocess,
            'pipeline_recipe': pipeline_recipe,
        }

        from molass_gui.rigorous_view import RigorousView
        RigorousView(self._decomp, self._trimmed, est_kwargs,
                     analysis_folder=folder, parent=self._win).show()
