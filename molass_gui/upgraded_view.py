"""UpgradedView — Phase 4: upgraded plot_components + method → RigorousView."""
import tkinter as tk
from tkinter import ttk

from molass_gui.plot_embed import embed_plot
from molass_gui.rgcurve_worker import start_rgcurve_worker
from molass_gui.params_dialog import show_parameters_lazy

_METHOD_LABELS = ['BH', 'DE']


class UpgradedView:
    def __init__(self, decomp, trimmed, nc, model_info, ctx, parent=None, app_root=None,
                 session_tag=None, rgcurve=None, score=None):
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
        ctx : SessionContext
            Accumulated GUI choices, for "Export to Notebook…".
        parent : tk widget or None
        app_root : App or None
            Root window; its close_session() tears down the whole session.
        session_tag : str or None
            Data folder name, shown in the title to distinguish concurrent sessions.
        rgcurve : RgCurve or None
            Already-computed Rg curve (from QuickView), if ready -- shown immediately.
            If None, computed here in the background and overlaid once ready.
        score : Score or None
            Already-built Score (from QuickView's Skip path, same decomp), if any --
            reused for "Show Parameters" instead of rebuilding. None on the Upgrade
            path, since the model (and thus the optimizer) has changed.
        """
        self._decomp = decomp
        self._trimmed = trimmed
        self._nc = nc
        self._model_info = model_info
        self._ctx = ctx
        self._parent = parent
        self._app_root = app_root
        self._session_tag = session_tag
        self._rgcurve = rgcurve
        self._score = score
        self._plot_state = None

    def show(self):
        win = tk.Toplevel(self._parent)
        model = self._model_info['model'].upper()
        title = f"Upgraded View \u2014 {model}"
        if self._session_tag:
            title += f"  [{self._session_tag}]"
        win.title(title)
        win.protocol("WM_DELETE_WINDOW", self._app_root.close_session)

        # Header: method + Rigorous button
        hdr = ttk.Frame(win, padding=(8, 4))
        hdr.pack(fill=tk.X)

        ttk.Label(hdr, text="Method:").pack(side=tk.LEFT)
        self._method_var = tk.StringVar(value='BH')
        ttk.Combobox(hdr, textvariable=self._method_var, values=_METHOD_LABELS,
                     state='readonly', width=8).pack(side=tk.LEFT, padx=4)

        self._rig_btn = ttk.Button(hdr, text="Rigorous Optimization\u2026",
                                   command=self._proceed_rigorous, style="Accent.TButton")
        self._rig_btn.pack(side=tk.RIGHT, padx=8)
        if self._rgcurve is None:
            # RigorousView would otherwise start its own concurrent get_rg_curve()
            # on this same decomp if clicked before our own background compute finishes.
            self._rig_btn.state(["disabled"])
        self._params_btn = ttk.Button(hdr, text="Show Parameters\u2026",
                                      command=self._show_parameters, state="disabled")
        self._params_btn.pack(side=tk.RIGHT, padx=8)
        ttk.Button(hdr, text="Export to Notebook\u2026",
                  command=self._export_to_notebook).pack(side=tk.RIGHT, padx=8)
        if self._rgcurve is not None:
            self._params_btn.state(["!disabled"])
        self._status_var = tk.StringVar(value="")
        ttk.Label(hdr, textvariable=self._status_var, foreground="gray").pack(
            side=tk.LEFT, padx=8)
        self._rg_var = tk.StringVar(value="")
        ttk.Label(hdr, textvariable=self._rg_var, foreground="gray").pack(
            side=tk.LEFT, padx=8)

        # Show plot_components for the current model; overlay Rg curve immediately if
        # QuickView already computed it, otherwise compute it here in the background.
        result = self._decomp.plot_components(rgcurve=self._rgcurve, rg_cmap='YlGn',
                                              rg_alpha_by_score=True, rg_alpha_power=2.5)
        self._plot_state = embed_plot(win, result.fig)
        self._win = win

        if self._rgcurve is None:
            start_rgcurve_worker(win, self._decomp, self._rg_var, self._on_rgcurve_ready)

    def _on_rgcurve_ready(self, rgcurve):
        self._rgcurve = rgcurve
        result = self._decomp.plot_components(rgcurve=rgcurve, rg_cmap='YlGn',
                                              rg_alpha_by_score=True, rg_alpha_power=2.5)
        self._plot_state = embed_plot(self._win, result.fig, previous=self._plot_state)
        self._rig_btn.state(["!disabled"])
        self._params_btn.state(["!disabled"])

    def _show_parameters(self):
        show_parameters_lazy(self, self._win, self._status_var, self._decomp, self._trimmed)

    def _export_to_notebook(self):
        from molass_gui.notebook_export import export_and_open
        export_and_open(self._ctx, self._win)

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

        # RigorousView(...).show() below runs synchronously (no background
        # thread), so the disabled state must be forced onto screen with
        # update_idletasks() -- otherwise Tk never gets an idle moment to
        # repaint it until RigorousView is already done, making the click
        # look ignored (same fix as QuickView._skip()).
        self._rig_btn.state(["disabled"])
        self._win.update_idletasks()

        decomp_params = {}
        if getattr(self._ctx, 'use_proportions', False):
            # Mirrors NaiveView's decomposition choice so the rigorous-optimization
            # subprocess (RecipeRunner.quick_decomposition(**decomp_params)) re-derives
            # the same, correctly-initialized decomposition instead of silently
            # falling back to the unstable default for high-overlap datasets.
            decomp_params['proportions'] = [1] * self._nc
        pipeline_recipe = {
            'num_components': self._nc,
            'model': model_key,
            'method': method,
            'decomp_params': decomp_params,
            'trim_params': {},
            'baseline_params': {},
        }
        if pore_dist is not None:
            pipeline_recipe['pore_dist'] = pore_dist
        if ln_pore_sigma is not None:
            pipeline_recipe['ln_pore_sigma'] = ln_pore_sigma

        est_kwargs = {
            'pipeline_recipe': pipeline_recipe,
        }

        self._ctx.method = method
        self._ctx.analysis_folder = folder

        from molass_gui.rigorous_view import RigorousView
        RigorousView(self._decomp, self._trimmed, est_kwargs,
                     analysis_folder=folder, ctx=self._ctx, parent=self._win,
                     app_root=self._app_root, session_tag=self._session_tag,
                     score=self._score).show()
        self._win.withdraw()  # unmap, not just minimize -- iconify() still leaves a taskbar thumbnail
