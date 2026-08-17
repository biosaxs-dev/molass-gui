"""QuickView — Phase 3: plot_components (EGH) + model selection → Upgrade / Skip → UpgradedView."""
import threading
import tkinter as tk
from tkinter import ttk

# (label, recipe model key, pore_dist kwarg or None)
_MODEL_OPTIONS = [
    ('EGH',                        'egh',  None),
    ('EGH \u2192 SDM (mono)',       'sdm',  None),
    ('EGH \u2192 SDM (lognormal)',  'sdm',  'lognormal'),
    ('EGH \u2192 EDM',              'cedm', None),
    ('EGH \u2192 LKM',              'lkm',  None),
    ('EGH \u2192 GRM',              'grm',  None),
]
_MODEL_LABELS = [m[0] for m in _MODEL_OPTIONS]


class QuickView:
    def __init__(self, decomp, trimmed, nc, parent=None, app_root=None, session_tag=None):
        self._decomp = decomp
        self._trimmed = trimmed
        self._nc = nc
        self._parent = parent
        self._app_root = app_root
        self._session_tag = session_tag

    def show(self):
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

        win = tk.Toplevel(self._parent)
        title = "Quick Optimization View"
        if self._session_tag:
            title += f"  [{self._session_tag}]"
        win.title(title)
        win.protocol("WM_DELETE_WINDOW", self._app_root.close_session)

        # Header: model selection + PSD σ (conditional) + Upgrade / Skip buttons
        hdr = ttk.Frame(win, padding=(8, 4))
        hdr.pack(fill=tk.X)

        ttk.Label(hdr, text="Model:").pack(side=tk.LEFT)
        self._model_var = tk.StringVar(value='EGH')
        self._model_cb = ttk.Combobox(hdr, textvariable=self._model_var, values=_MODEL_LABELS,
                                      state='readonly', width=24)
        self._model_cb.pack(side=tk.LEFT, padx=4)

        # PSD σ frame — shown only when SDM (lognormal) is selected
        self._psd_frame = ttk.Frame(hdr)
        ttk.Label(self._psd_frame, text="PSD \u03c3:").pack(side=tk.LEFT, padx=(8, 0))
        self._psd_sigma_var = tk.StringVar(value="0.1")
        ttk.Entry(self._psd_frame, textvariable=self._psd_sigma_var, width=6).pack(
            side=tk.LEFT, padx=4)

        self._action_btn = ttk.Button(hdr, text="Skip", command=self._skip,
                                      style="Accent.TButton")
        self._action_btn.pack(side=tk.RIGHT, padx=8)
        self._status_var = tk.StringVar(value="")
        ttk.Label(hdr, textvariable=self._status_var, foreground="gray").pack(
            side=tk.LEFT, padx=8)

        def _on_model_change(*_):
            label = self._model_var.get()
            is_ln = label == 'EGH \u2192 SDM (lognormal)'
            if is_ln:
                self._psd_frame.pack(side=tk.LEFT, after=self._model_cb)
            else:
                self._psd_frame.pack_forget()
            _, key, _ = next(m for m in _MODEL_OPTIONS if m[0] == label)
            if key == 'egh':
                self._action_btn.configure(text='Skip', command=self._skip)
            else:
                self._action_btn.configure(text='Upgrade', command=self._upgrade)
        self._model_var.trace_add('write', _on_model_change)

        # Show EGH plot_components immediately
        result = self._decomp.plot_components()
        canvas = FigureCanvasTkAgg(result.fig, master=win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        NavigationToolbar2Tk(canvas, win).update()
        self._win = win

    def _skip(self):
        model_info = {'model': 'egh', 'pore_dist': None, 'ln_pore_sigma': None}
        from molass_gui.upgraded_view import UpgradedView
        UpgradedView(self._decomp, self._trimmed, self._nc, model_info,
                     parent=self._win, app_root=self._app_root,
                     session_tag=self._session_tag).show()

    def _upgrade(self):
        model_label = self._model_var.get()
        _, model_key, pore_dist = next(m for m in _MODEL_OPTIONS if m[0] == model_label)
        if model_key == 'egh':
            self._skip()
            return
        ln_pore_sigma = float(self._psd_sigma_var.get()) if pore_dist == 'lognormal' else None
        self._action_btn.state(["disabled"])
        self._status_var.set(f"Upgrading to {model_key.upper()}\u2026")

        def worker():
            try:
                upgrade_kwargs = {}
                if pore_dist is not None:
                    upgrade_kwargs['pore_dist'] = pore_dist
                    if ln_pore_sigma is not None:
                        upgrade_kwargs['model_params'] = {'ln_pore_sigma': ln_pore_sigma}
                upgraded = self._decomp.upgrade(model_key, **upgrade_kwargs)
                model_info = {'model': model_key, 'pore_dist': pore_dist,
                              'ln_pore_sigma': ln_pore_sigma}

                def on_main():
                    self._action_btn.state(["!disabled"])
                    self._status_var.set("")
                    from molass_gui.upgraded_view import UpgradedView
                    UpgradedView(upgraded, self._trimmed, self._nc, model_info,
                                 parent=self._win, app_root=self._app_root,
                                 session_tag=self._session_tag).show()

                self._win.after(0, on_main)
            except Exception as exc:
                msg = str(exc)
                def on_error(m=msg):
                    self._status_var.set(f"Error: {m}")
                    self._action_btn.state(["!disabled"])
                self._win.after(0, on_error)

        threading.Thread(target=worker, daemon=True).start()
