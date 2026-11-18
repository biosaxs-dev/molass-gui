"""Continue as new analysis... (molass-library#396, ``molass.fork_analysis``): start a new analysis folder from the
best result of the one that is open, under the same elution model or another.

A small dialog collects the model, "start near the current curves", the new folder, a note, the method and the
number of jobs. **Prepare** builds the plan on the main thread under the busy signal (the model change and the curve
matching take seconds, the score of the start more) and shows what job 000 would start from; **Start** hands the
prepared plan to the caller, which opens a live run window for it. Nothing is written to disk before Start.
"""
import os
import tkinter as tk
from tkinter import ttk

from molass_gui import busy, fork_logic
from molass_gui.model_names import model_display_name

TITLE = "Continue as new analysis"


def fork_available():
    """Whether the installed molass has ``molass.fork_analysis`` (molass-library#396)."""
    try:
        from molass.Rigorous import ForkAnalysis  # noqa: F401
        return True
    except ImportError:
        return False


class ForkContext:
    """What the dialog needs of the open analysis; ``source_info()`` loads the best result once."""

    def __init__(self, analysis_folder, decomp, trimmed, recipe, rgcurve=None):
        self.analysis_folder = analysis_folder
        self.decomp = decomp
        self.trimmed = trimmed
        self.recipe = recipe or {}
        self.rgcurve = rgcurve
        self._info = None

    @property
    def source_model(self):
        return str(self.recipe.get('model') or 'egh').lower()

    @property
    def method(self):
        return str(self.recipe.get('method') or 'bh').upper()

    def source_info(self):
        if self._info is None:
            from molass.Rigorous.ForkAnalysis import fork_source
            self._info = fork_source(self.analysis_folder, self.decomp, self.trimmed, self.recipe,
                                     rgcurve=self.rgcurve)
        return self._info


class ForkDialog:
    def __init__(self, win, status_var, ctx, on_start, jobs_default=10):
        self._parent = win
        self._main_status_var = status_var
        self._ctx = ctx
        self._on_start = on_start
        self._jobs_default = jobs_default
        self._prepared = None

    def show(self):
        ctx = self._ctx
        dlg = tk.Toplevel(self._parent)
        dlg.title(TITLE)
        dlg.resizable(False, False)
        self._dlg = dlg
        f = ttk.Frame(dlg, padding=12)
        f.pack(fill=tk.BOTH, expand=True)

        keys = fork_logic.model_choices(ctx.source_model)
        self._labels = {self._label(k): k for k in keys}
        self._model_var = tk.StringVar(value=self._label(keys[1] if len(keys) > 1 else keys[0]))
        self._match_var = tk.BooleanVar(value=False)
        self._folder_var = tk.StringVar(value="")
        self._note_var = tk.StringVar(value="")
        self._method_var = tk.StringVar(value=ctx.method if ctx.method in fork_logic.METHODS else 'BH')
        self._jobs_var = tk.StringVar(value=str(self._jobs_default))
        self._status_var = tk.StringVar(value="")

        row = 0
        ttk.Label(f, text="Start from the best result of:").grid(row=row, column=0, sticky=tk.W, pady=2)
        ttk.Label(f, text=os.path.basename(os.path.normpath(ctx.analysis_folder)) or ctx.analysis_folder,
                  font=("", 10, "bold")).grid(row=row, column=1, columnspan=2, sticky=tk.W, padx=6)
        row += 1
        ttk.Label(f, text="Elution model:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self._model_box = ttk.Combobox(f, textvariable=self._model_var, values=list(self._labels), state="readonly",
                                       width=14)
        self._model_box.grid(row=row, column=1, sticky=tk.W, padx=6)
        ttk.Label(f, text=f"(this analysis: {self._label(ctx.source_model)})", foreground="gray").grid(
            row=row, column=2, sticky=tk.W)
        row += 1
        self._match_chk = ttk.Checkbutton(f, text="Start near the current curves (GRM, LKM)",
                                          variable=self._match_var)
        self._match_chk.grid(row=row, column=1, columnspan=2, sticky=tk.W, padx=6)
        row += 1
        ttk.Label(f, text="New folder:").grid(row=row, column=0, sticky=tk.W, pady=2)
        ttk.Entry(f, textvariable=self._folder_var, width=60).grid(row=row, column=1, columnspan=2, padx=6,
                                                                   sticky=tk.W)
        row += 1
        ttk.Label(f, text="Note:").grid(row=row, column=0, sticky=tk.W, pady=2)
        ttk.Entry(f, textvariable=self._note_var, width=60).grid(row=row, column=1, columnspan=2, padx=6,
                                                                 sticky=tk.W)
        row += 1
        opts = ttk.Frame(f)
        opts.grid(row=row, column=0, columnspan=3, sticky=tk.W, pady=2)
        ttk.Label(opts, text="Method:").pack(side=tk.LEFT)
        ttk.Combobox(opts, textvariable=self._method_var, values=list(fork_logic.METHODS), state="readonly",
                     width=6).pack(side=tk.LEFT, padx=4)
        ttk.Label(opts, text="Jobs:").pack(side=tk.LEFT, padx=(12, 0))
        ttk.Spinbox(opts, textvariable=self._jobs_var, from_=1, to=50, width=4, state="readonly").pack(
            side=tk.LEFT, padx=4)
        row += 1
        # a Label, not a Text: after the optimizer has been built (legacy imports) .configure() of widgets is unsafe
        # here (see rigorous_view.py), and a Label needs only its text variable
        self._preview_var = tk.StringVar(value="")
        self._preview = ttk.Label(f, textvariable=self._preview_var, justify=tk.LEFT, wraplength=560)
        self._preview.grid(row=row, column=0, columnspan=3, sticky=tk.W, pady=(8, 2))
        row += 1
        ttk.Label(f, textvariable=self._status_var, foreground="gray").grid(row=row, column=0, columnspan=3,
                                                                           sticky=tk.W)
        row += 1
        buttons = ttk.Frame(f)
        buttons.grid(row=row, column=0, columnspan=3, sticky=tk.E, pady=(8, 0))
        self._start_btn = ttk.Button(buttons, text="Start", command=self._start, state="disabled",
                                     style="Accent.TButton")
        self._start_btn.pack(side=tk.RIGHT, padx=4)
        self._prepare_btn = ttk.Button(buttons, text="Prepare", command=self._prepare)
        self._prepare_btn.pack(side=tk.RIGHT, padx=4)
        ttk.Button(buttons, text="Cancel", command=self._close).pack(side=tk.RIGHT, padx=4)

        self._on_model_change()
        for var in (self._model_var, self._match_var, self._folder_var, self._method_var, self._jobs_var):
            var.trace_add("write", self._invalidate)
        self._model_var.trace_add("write", self._on_model_change)
        dlg.protocol("WM_DELETE_WINDOW", self._close)
        dlg._fork_dialog = self          # the controller behind the window (tests drive it through this)
        return dlg

    # ------------------------------------------------------------------

    @staticmethod
    def _label(key):
        return model_display_name(key)

    def _model_key(self):
        return self._labels.get(self._model_var.get(), self._ctx.source_model)

    def _on_model_change(self, *_):
        key = self._model_key()
        available = fork_logic.match_available(self._ctx.source_model, key)
        self._match_chk.state(["!disabled"] if available else ["disabled"])
        if not available:
            self._match_var.set(False)
        # the suggested folder follows the model until the user has typed their own
        current = self._folder_var.get()
        if not current or current == getattr(self, "_suggested", None):
            self._suggested = fork_logic.default_new_folder(self._ctx.analysis_folder, key, self._ctx.source_model)
            self._folder_var.set(self._suggested)

    def _invalidate(self, *_):
        if self._prepared is not None:
            self._prepared = None
            self._start_btn.state(["disabled"])
            self._set_preview([])
            self._status_var.set("Changed: prepare again.")

    def _set_preview(self, lines):
        self._preview_var.set("\n".join(lines))

    def _prepare(self):
        ctx = self._ctx
        key = self._model_key()
        folder = self._folder_var.get().strip()
        problem = fork_logic.check_fields(ctx.source_model, key, self._match_var.get(), folder, ctx.analysis_folder)
        if problem:
            self._status_var.set(problem)
            return
        method = self._method_var.get()
        note = self._note_var.get().strip() or None
        try:
            with busy.working(self._dlg, self._status_var, "Preparing the new analysis\u2026",
                              buttons=[self._prepare_btn], key="fork-prepare"):
                from molass.Rigorous.ForkAnalysis import plan_fork
                info = ctx.source_info()
                plan = plan_fork(ctx.analysis_folder, folder, model=key, seed='auto',
                                 match_curves=bool(self._match_var.get()), method=method, note=note, info=info,
                                 optimize_kwargs=dict(async_=True, monitor=False))
                score = plan.score()
        except Exception as exc:
            from molass_gui.error_dialog import show_error_detail
            show_error_detail(self._dlg, self._status_var, str(exc) or type(exc).__name__,
                              title="Could not prepare the new analysis")
            return
        info = ctx.source_info()
        self._prepared = (plan, score)
        self._set_preview(fork_logic.summary_lines(plan, score, source_fv=getattr(info, 'fv', None),
                                                   source_sv=getattr(info, 'sv', None)))
        self._status_var.set("Ready: Start opens the run in a new window.")
        self._start_btn.state(["!disabled"])

    def _start(self):
        if self._prepared is None:
            return
        plan, score = self._prepared
        try:
            n_jobs = max(1, int(self._jobs_var.get()))
        except (ValueError, tk.TclError):
            n_jobs = 1
        method = self._method_var.get()
        self._close()
        self._on_start(plan, score, n_jobs, method)

    def _close(self):
        try:
            self._dlg.destroy()
        except tk.TclError:
            pass


def show_fork_dialog(win, status_var, ctx, on_start, previous=None, jobs_default=10):
    """Open the dialog (or raise the open one). ``on_start(plan, score, n_jobs, method)`` is called when the user
    presses Start; returns the dialog window."""
    if previous is not None:
        try:
            if previous.winfo_exists():
                previous.deiconify()
                previous.lift()
                return previous
        except tk.TclError:
            pass
    return ForkDialog(win, status_var, ctx, on_start, jobs_default=jobs_default).show()
