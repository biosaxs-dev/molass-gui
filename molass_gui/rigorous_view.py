"""RigorousView — Phase 5: Rg computation + auto-start optimization + live 4-panel monitor.

Receives an already-upgraded Decomposition from UpgradedView (Phase 4).
Transitions: computing Rg → scoring → running → done.
"""
import os
import traceback
import threading
import time
import tkinter as tk
from tkinter import ttk

from molass_gui.params_dialog import show_parameters_lazy
from molass_gui.plot_components_dialog import show_plot_components_lazy
from molass_gui.shape_analysis_dialog import show_shape_analysis_lazy
from molass_gui.denss_view import show_denss_lazy
from molass_gui.ranks_dialog import show_set_ranks_lazy
from molass_gui.window_tree import register_window_cleanup, register_close_guard

_NUM_JOBS_DEFAULT = 10  # matches upgraded_view.py's New Analysis default


class RigorousView:
    def __init__(self, decomp, trimmed, est_kwargs, analysis_folder, ctx=None, parent=None,
                 app_root=None, session_tag=None, score=None):
        """
        Parameters
        ----------
        decomp : Decomposition
            EGH decomposition; Rg curve already cached by QuickView.
        trimmed : SecSaxsData
            Trimmed (uncorrected) SSD, passed to score().
        est_kwargs : dict
            Keys: pipeline_recipe.
        analysis_folder : str
            Output folder for optimization results.
        ctx : SessionContext or None
            Accumulated GUI choices, for "Export to Notebook…".
        parent : tk widget or None
        app_root : App or None
            Root window; its close_session() tears down the whole session.
        session_tag : str or None
            Data folder name, shown in the title to distinguish concurrent sessions.
        score : Score or None
            Already-built Score (from UpgradedView), if any -- reused instead of
            rebuilding in _prep_main.
        """
        self._decomp = decomp
        self._trimmed = trimmed
        self._est_kwargs = est_kwargs
        self._analysis_folder = analysis_folder
        self._ctx = ctx
        self._parent = parent
        self._app_root = app_root
        self._session_tag = session_tag
        self._decomp_for_opt = None
        self._score = score
        self._run_info = None
        self._stopped = False
        self._niter = 0
        self._round_base_n = 0  # cumulative evals that existed before this batch of jobs started
        self._method = 'BH'
        self._num_jobs = max(1, int(est_kwargs.get('num_jobs', 1)))
        self._job_round = 0
        self._last_sv_len = 0
        self._redraw_event = threading.Event()
        self._result_mode = False
        self._result_best_params = None
        # Ephemeral per-component rank override (see ranks_dialog.py) -- applied
        # to whichever result Plot Components/Shape Analysis/Run DENSS next
        # (re)loads; not written back to recipe.json.
        self._xr_ranks = None

    @classmethod
    def open_existing(cls, analysis_folder, parent=None, app_root=None, session_tag=None):
        """Build a RigorousView showing the best completed result for an
        already-existing analysis_folder (Open Existing Analysis path), with
        a Resume button in place of the usual auto-start.

        decomp/trimmed/est_kwargs are not known yet at construction time --
        they get rebuilt from recipe.json inside _prep_main_result().
        """
        view = cls(None, None, {}, analysis_folder, ctx=None,
                   parent=parent, app_root=app_root, session_tag=session_tag)
        view._result_mode = True
        return view

    def show(self):
        import matplotlib.pyplot as plt
        import matplotlib.gridspec as gridspec
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

        win = tk.Toplevel(self._parent)
        recipe = (self._est_kwargs.get('pipeline_recipe') or {})
        model  = recipe.get('model', 'egh').upper()
        method = recipe.get('method', 'bh').upper()
        self._method = method
        if self._result_mode:
            title = "Rigorous Optimization Result"
        else:
            title = f"Rigorous Optimization — {model} | {method}"
        if self._session_tag:
            title += f"  [{self._session_tag}]"
        win.title(title)
        win.protocol("WM_DELETE_WINDOW", self._app_root.close_session)
        register_window_cleanup(
            win, lambda: self._run_info.stop() if self._run_info is not None else None)
        register_close_guard(
            win, lambda: self._run_info is not None and self._run_info.is_alive,
            "Rigorous optimization run in progress")

        # Prep phase header (hidden after prep completes)
        self._prep_frame = ttk.Frame(win, padding=(8, 2))
        self._prep_frame.pack(fill=tk.X)
        if self._result_mode:
            self._prep_var = tk.StringVar(value="Loading existing analysis\u2026")
            n_frames = 1
        else:
            self._prep_var = tk.StringVar(value="Computing Rg curve\u2026")
            n_frames = len(self._decomp.ssd.xr.jv)
        ttk.Label(self._prep_frame, textvariable=self._prep_var).pack(side=tk.LEFT)
        self._pb = ttk.Progressbar(self._prep_frame, maximum=n_frames, length=300)
        self._pb.pack(side=tk.LEFT, padx=8, fill=tk.X, expand=True)

        # Optimization header (SV, evals, action button)
        hdr = ttk.Frame(win, padding=(8, 4))
        hdr.pack(fill=tk.X)
        self._status_var = tk.StringVar(value="")
        ttk.Label(hdr, textvariable=self._status_var, width=24).pack(side=tk.LEFT)
        self._sv_var = tk.StringVar(value="SV: \u2014")
        ttk.Label(hdr, textvariable=self._sv_var, font=("", 12, "bold")).pack(
            side=tk.LEFT, padx=16)
        self._n_var = tk.StringVar(value="0 evals")
        ttk.Label(hdr, textvariable=self._n_var).pack(side=tk.LEFT)
        self._iter_var = tk.StringVar(value="Iter: \u2014")
        ttk.Label(hdr, textvariable=self._iter_var).pack(side=tk.LEFT, padx=12)
        self._time_var = tk.StringVar(value="")
        ttk.Label(hdr, textvariable=self._time_var, foreground="#555").pack(side=tk.LEFT, padx=4)
        # Terminate <-> Resume are two mutually-exclusive button rows, swapped
        # via pack()/pack_forget() (never .configure() -- some molass-legacy
        # import triggered during score()'s construction (python-tkdnd/
        # ttkwidgets globally patches ttk.Widget.configure for drag-and-drop
        # hooks) makes .configure() crash on ANY button afterwards with
        # AttributeError('...widgethook_...'); .state()/.pack()/.pack_forget()
        # and creating new widgets are all unaffected, confirmed empirically).
        # Both rows are always created so the SAME swap
        # (_show_running_controls()/_show_resumable_controls()) works whether
        # we're entering the resumable state from a fresh Open Existing
        # Analysis load, or from a live run completing/failing/being
        # Terminated -- not just once at startup.
        self._action_btn = ttk.Button(hdr, text="Terminate", command=self._stop,
                                      state='disabled', style="Danger.TButton")
        self._resume_btn = ttk.Button(hdr, text="Resume", command=self._resume,
                                      style="Accent.TButton")
        self._resume_jobs_var = tk.StringVar(value=str(_NUM_JOBS_DEFAULT))
        self._resume_jobs_spin = ttk.Spinbox(hdr, textvariable=self._resume_jobs_var,
                                             from_=1, to=50, width=4, state='readonly')
        self._resume_jobs_label = ttk.Label(hdr, text="Jobs:")
        self._params_btn = ttk.Button(hdr, text="Show Parameters\u2026",
                                      command=self._show_parameters, state="disabled")
        self._plotcomp_btn = ttk.Button(hdr, text="Plot Components\u2026",
                                        command=self._plot_components, state="disabled")
        self._shapeanalysis_btn = ttk.Button(hdr, text="Shape Analysis\u2026",
                                            command=self._shape_analysis, state="disabled")
        self._denss_btn = ttk.Button(hdr, text="Run DENSS\u2026",
                                     command=self._run_denss, state="disabled")
        self._ranks_btn = ttk.Button(hdr, text="Set Ranks\u2026",
                                     command=self._set_ranks, state="disabled")
        if self._result_mode:
            self._show_resumable_controls()
        else:
            self._show_running_controls()
        if self._ctx is not None:
            ttk.Button(hdr, text="Export to Notebook\u2026",
                      command=self._export_to_notebook).pack(side=tk.RIGHT, padx=8)
        if self._score is not None:
            self._params_btn.state(["!disabled"])
            self._plotcomp_btn.state(["!disabled"])
            self._shapeanalysis_btn.state(["!disabled"])
            self._denss_btn.state(["!disabled"])
            self._ranks_btn.state(["!disabled"])

        ttk.Label(win, text=f"Output: {self._analysis_folder}", foreground="gray",
                  padding=(8, 0)).pack(fill=tk.X, anchor=tk.W)

        # 5-panel figure: top 3 panels + Function SV row + Rg Values row
        self._fig = plt.figure(figsize=(18, 8.0))
        gs = gridspec.GridSpec(3, 3, figure=self._fig,
                               height_ratios=[4, 1.5, 1.5], hspace=0.55)
        self._ax_uv      = self._fig.add_subplot(gs[0, 0])
        self._ax_xr      = self._fig.add_subplot(gs[0, 1])
        self._ax_score   = self._fig.add_subplot(gs[0, 2])
        self._ax_xr_twin = self._ax_xr.twinx()
        self._ax_xr_twin.grid(False)
        self._ax_sv      = self._fig.add_subplot(gs[1, :])
        self._ax_rg      = self._fig.add_subplot(gs[2, :])
        self._axis_info  = (self._fig,
                            (self._ax_uv, self._ax_xr, self._ax_score, self._ax_xr_twin))

        canvas = FigureCanvasTkAgg(self._fig, master=win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        NavigationToolbar2Tk(canvas, win).update()
        self._canvas = canvas
        self._win = win

        self._win.after(10, self._prep_main_result if self._result_mode else self._prep_main)

    # ------------------------------------------------------------------
    # Prep phase

    def _prep_main(self):
        """Main-thread: kick off Rg curve computation in a background thread
        (same safe queue/after() hand-off as QuickView/UpgradedView's
        rgcurve_worker -- get_rg_curve() itself has no Tk/matplotlib touches,
        unlike score(), which stays on the main thread in _on_rg_ready below).
        Usually an instant cache hit (already computed by QuickView/
        UpgradedView), but must not assume that -- e.g. Skip/Upgrade always
        preserve/rebuild xr_ranks now, and a still-running prior worker or a
        cache miss would otherwise block the whole GUI for the full
        per-frame Guinier fit.
        """
        from molass_gui.rgcurve_worker import start_rgcurve_worker

        def _progress(j, n):
            self._pb['value'] = j

        start_rgcurve_worker(self._win, self._decomp, None, self._on_rg_ready,
                             progress_cb=_progress)

    def _on_rg_ready(self, rgcurve):
        try:
            self._decomp_for_opt = self._decomp
            if self._score is None:
                self._prep_var.set("Building optimizer\u2026")
                self._win.update_idletasks()
                self._score = self._decomp_for_opt.score(trimmed_ssd=self._trimmed)
            self._on_prep_done(self._score)
        except Exception as exc:
            short = str(exc).split('\n')[0][:120]
            self._prep_var.set(f"Prep error: {short}")

    def _on_prep_done(self, score):
        self._score = score
        self._pb.stop()
        self._prep_frame.pack_forget()
        try:
            opt = score.optimizer
            opt.objective_func(score.init_params, plot=True, axis_info=self._axis_info)
            _retitle_panels(self._ax_uv, self._ax_xr, self._ax_score, score.sv)
            _draw_sv_history(self._ax_sv, [], 0)
            _draw_rg_history(self._ax_rg, [], 0)
        except Exception:
            pass
        self._canvas.draw()
        self._status_var.set(f"Ready \u2014 SV={score.sv:.2f}")
        self._sv_var.set(f"SV: {score.sv:.2f}")
        self._params_btn.state(["!disabled"])
        self._plotcomp_btn.state(["!disabled"])
        self._shapeanalysis_btn.state(["!disabled"])
        self._denss_btn.state(["!disabled"])
        self._ranks_btn.state(["!disabled"])
        self._optimize()  # auto-start; user can Terminate if needed

    def _prep_main_result(self):
        """Main-thread: rebuild the pipeline from recipe.json, then kick off
        Rg curve computation in a background thread (see _prep_main's
        comment), then draw the best completed result (Open Existing
        Analysis path). No auto-start -- the header's action button offers
        Resume instead.
        """
        try:
            from molass.Rigorous.RecipeRunner import rebuild_decomposition_from_recipe

            ssd, trimmed, decomp, recipe = rebuild_decomposition_from_recipe(self._analysis_folder)
            self._decomp = decomp
            self._decomp_for_opt = decomp
            self._trimmed = trimmed
            self._est_kwargs = {'pipeline_recipe': recipe}
            self._method = recipe.get('method', 'bh').upper()

            self._prep_var.set("Computing Rg curve\u2026")
            self._win.update_idletasks()

            from molass_gui.rgcurve_worker import start_rgcurve_worker
            start_rgcurve_worker(self._win, decomp, None, self._on_rg_ready_result)
        except Exception as exc:
            short = str(exc).split('\n')[0][:120]
            self._prep_var.set(f"Load error: {short}")

    def _on_rg_ready_result(self, rgcurve):
        try:
            from molass.Rigorous.RigorousImplement import find_global_best_params
            from molass.Rigorous.CurrentStateUtils import fv_to_sv

            recipe = self._est_kwargs.get('pipeline_recipe') or {}
            self._prep_var.set("Building optimizer\u2026")
            self._win.update_idletasks()
            score = self._decomp.score(trimmed_ssd=self._trimmed,
                                       function_code=recipe.get('function_code'))

            jobs_dir = os.path.join(self._analysis_folder, "optimized", "jobs")
            best_params, best_fv, best_job = find_global_best_params(jobs_dir, score.init_params)
            if best_params is None:
                best_params, best_fv = score.init_params, score.fv

            self._on_prep_done_result(score, best_params, float(fv_to_sv(best_fv)))
        except Exception as exc:
            short = str(exc).split('\n')[0][:120]
            self._prep_var.set(f"Load error: {short}")

    def _on_prep_done_result(self, score, best_params, sv):
        self._score = score
        self._result_best_params = best_params
        self._pb.stop()
        self._prep_frame.pack_forget()
        try:
            opt = score.optimizer
            opt.objective_func(best_params, plot=True, axis_info=self._axis_info)
            _retitle_panels(self._ax_uv, self._ax_xr, self._ax_score, sv)
        except Exception:
            pass
        # History panels are disk-based -- RunInfo.reconnect() works without a
        # live optimizer for sv_history, but rg_history needs optimizer.params_type
        # (confirmed empirically -- reconnect()'s docstring only promises
        # sv_history/live_status/load_best), so attach our own real one.
        try:
            from molass.Rigorous.RunInfo import RunInfo
            run_info = RunInfo.reconnect(self._analysis_folder, raise_if_not_found=False)
            if run_info is not None:
                run_info.optimizer = score.optimizer
            sv_hist  = run_info.sv_history if run_info is not None else []
            raw_hist = run_info.sv_history_raw if run_info is not None else None
            rg_hist  = run_info.rg_history if run_info is not None else []
        except Exception:
            sv_hist, raw_hist, rg_hist = [], None, []
        _draw_sv_history(self._ax_sv, sv_hist, 0, raw=raw_hist)
        _draw_rg_history(self._ax_rg, rg_hist, 0)
        self._canvas.draw()
        self._status_var.set(f"Loaded \u2014 SV={sv:.2f}")
        self._sv_var.set(f"SV: {sv:.2f}")
        self._params_btn.state(["!disabled"])
        self._plotcomp_btn.state(["!disabled"])
        self._shapeanalysis_btn.state(["!disabled"])
        self._denss_btn.state(["!disabled"])
        self._ranks_btn.state(["!disabled"])
        # self._resume_btn was created already-enabled in show() -- no further
        # action needed here (and no .configure()/.state() call on it, since
        # this runs right after the .configure()-breaking import; see show()).

    def _show_running_controls(self):
        """Terminate row visible (disabled until _on_started re-enables it);
        Resume/Jobs hidden. Re-packs _params_btn/_plotcomp_btn/etc together
        with _action_btn (not just _action_btn alone): pack(side=RIGHT) orders
        slaves by *packing call* order, not creation order -- packing only one
        of several buttons would reverse their relative on-screen order."""
        self._resume_btn.pack_forget()
        self._resume_jobs_spin.pack_forget()
        self._resume_jobs_label.pack_forget()
        self._params_btn.pack_forget()
        self._plotcomp_btn.pack_forget()
        self._shapeanalysis_btn.pack_forget()
        self._denss_btn.pack_forget()
        self._ranks_btn.pack_forget()
        self._action_btn.pack(side=tk.RIGHT, padx=8)
        self._params_btn.pack(side=tk.RIGHT, padx=8)
        self._plotcomp_btn.pack(side=tk.RIGHT, padx=8)
        self._shapeanalysis_btn.pack(side=tk.RIGHT, padx=8)
        self._denss_btn.pack(side=tk.RIGHT, padx=8)
        self._ranks_btn.pack(side=tk.RIGHT, padx=8)
        self._action_btn.state(["disabled"])

    def _show_resumable_controls(self):
        """Resume/Jobs row visible; Terminate hidden -- the state a live run
        reaches once terminated/completed/failed, unifying it with the state
        Open Existing Analysis already starts in, instead of being a dead end
        that requires closing the window and reloading from disk."""
        self._action_btn.pack_forget()
        self._params_btn.pack_forget()
        self._plotcomp_btn.pack_forget()
        self._shapeanalysis_btn.pack_forget()
        self._denss_btn.pack_forget()
        self._ranks_btn.pack_forget()
        self._resume_btn.pack(side=tk.RIGHT, padx=8)
        self._resume_jobs_spin.pack(side=tk.RIGHT, padx=(0, 4))
        self._resume_jobs_label.pack(side=tk.RIGHT, padx=(8, 0))
        self._params_btn.pack(side=tk.RIGHT, padx=8)
        self._plotcomp_btn.pack(side=tk.RIGHT, padx=8)
        self._shapeanalysis_btn.pack(side=tk.RIGHT, padx=8)
        self._denss_btn.pack(side=tk.RIGHT, padx=8)
        self._ranks_btn.pack(side=tk.RIGHT, padx=8)

    def _resume(self):
        # Reset _stopped -- may still be True from a previous terminal state
        # (completed/failed/Terminated) that led here; _launch_resume/
        # _watch_tick/_ui_poll all bail out immediately while it's set.
        self._stopped = False
        self._show_running_controls()
        self._status_var.set("Starting\u2026")
        # Read the Spinbox on the main thread -- Tk variables aren't safe to
        # touch from the background thread that _launch_resume runs on.
        try:
            self._resume_jobs_n = max(1, int(self._resume_jobs_var.get()))
        except (ValueError, tk.TclError):
            self._resume_jobs_n = 1
        threading.Thread(target=self._launch_resume, daemon=True).start()

    def _launch_resume(self):
        """Continue an existing analysis_folder's job history for N more rounds.

        clear_jobs=False is required here (not just num_jobs=1's default path):
        Decomposition.optimize_rigorously(num_jobs>1) hardcodes clear_jobs=True
        for its own first round, which would wipe the history we just loaded --
        so this loops manually (clear_jobs=False every round) instead of
        delegating to the library's num_jobs loop, per its own docstring's
        recommendation for exactly this case. _ui_poll already drives the
        'Job X/Y' display and per-round completion generically off
        self._job_round/self._num_jobs, same as the New Analysis num_jobs>1 path.
        """
        try:
            pipeline_recipe = self._est_kwargs.get('pipeline_recipe', None)
            method = (pipeline_recipe or {}).get('method', 'BH').upper()
            n = getattr(self, '_resume_jobs_n', 1)
            for round_idx in range(n):
                if self._stopped:
                    break
                run_info = self._decomp_for_opt.optimize_rigorously(
                    trimmed_ssd=self._trimmed,
                    async_=True,
                    monitor=False,
                    method=method,
                    analysis_folder=self._analysis_folder,
                    pipeline_recipe=pipeline_recipe,
                    clear_jobs=False,
                )
                self._job_round = round_idx + 1
                self._num_jobs = n
                self._last_sv_len = 0
                self._run_info = run_info
                if round_idx == 0:
                    # Same one-time, whole-batch base capture as _on_round_start
                    # (New Analysis num_jobs>1 path) -- see comment there.
                    try:
                        self._round_base_n = len(run_info.sv_history)
                    except Exception:
                        self._round_base_n = 0
                    self._win.after(0, self._on_started)
                run_info.wait(timeout=0)
        except Exception as exc:
            tb = traceback.format_exc()
            log_path = os.path.join(self._analysis_folder, 'molass_gui_error.log')
            try:
                os.makedirs(self._analysis_folder, exist_ok=True)
                with open(log_path, 'w') as f:
                    f.write(tb)
            except Exception:
                pass
            short = str(exc).split('\n')[0][:120]
            self._win.after(0, lambda m=short: self._status_var.set(
                f"Error: {m}  \u2014 see {log_path}"))

    def _show_parameters(self):
        # run_info.best_params reflects the live/final run once one exists;
        # falls back to the loaded result's best params (Open Existing
        # Analysis, before Resume), then the initial score's params.
        params = None
        if self._run_info is not None:
            params = self._run_info.best_params
        elif self._result_best_params is not None:
            params = self._result_best_params
        show_parameters_lazy(self, self._win, self._status_var, self._decomp_for_opt,
                             self._trimmed, params=params)

    def _plot_components(self):
        # Always reloads the latest completed job from disk (not cached) --
        # the current best may have improved since this was last opened,
        # especially right after Resume produces new jobs.
        rgcurve = self._decomp_for_opt.get_rg_curve()
        show_plot_components_lazy(self._win, self._status_var, self._decomp_for_opt,
                                  self._analysis_folder, rgcurve=rgcurve,
                                  xr_ranks=self._xr_ranks)

    def _shape_analysis(self):
        rgcurve = self._decomp_for_opt.get_rg_curve()
        show_shape_analysis_lazy(self._win, self._status_var, self._decomp_for_opt,
                                 self._analysis_folder, rgcurve=rgcurve,
                                 xr_ranks=self._xr_ranks)

    def _run_denss(self):
        rgcurve = self._decomp_for_opt.get_rg_curve()
        show_denss_lazy(self._win, self._status_var, self._decomp_for_opt,
                        self._analysis_folder, rgcurve=rgcurve, xr_ranks=self._xr_ranks)

    def _set_ranks(self):
        # Prefer an override already chosen via this dialog; otherwise fall
        # back to whatever ranks the decomp already carries (e.g. propagated
        # from QuickView's Ranks entry through Skip/Upgrade) so the dialog
        # reflects the actually-effective setting, not just this view's own
        # override state.
        current = self._xr_ranks
        if current is None:
            current = getattr(self._decomp_for_opt, 'xr_ranks', None)
        show_set_ranks_lazy(self._win, self._decomp_for_opt.num_components,
                            current, self._on_ranks_applied)

    def _on_ranks_applied(self, ranks):
        self._xr_ranks = ranks
        self._status_var.set(
            f"Ranks set to {ranks} \u2014 applies next time Plot Components/"
            "Shape Analysis/Run DENSS is (re)opened")

    def _export_to_notebook(self):
        from molass_gui.notebook_export import export_and_open
        export_and_open(self._ctx, self._win)

    # ------------------------------------------------------------------
    # Optimization phase

    def _optimize(self):
        self._status_var.set("Starting\u2026")
        threading.Thread(target=self._launch, daemon=True).start()

    def _launch(self):
        try:
            pipeline_recipe = self._est_kwargs.get('pipeline_recipe', None)
            method = (pipeline_recipe or {}).get('method', 'BH').upper()

            def _on_round_start(round_idx, num_jobs, run_info):
                self._job_round = round_idx + 1
                self._run_info = run_info
                self._last_sv_len = 0  # fresh SV-history trace for this round
                if round_idx == 0:
                    # sv_history is cumulative across all jobs in analysis_folder --
                    # capture its length once, before this whole batch's evals land,
                    # so the plot's ceiling (_ui_poll) spans the entire planned
                    # batch (all num_jobs rounds), not just the round in progress.
                    try:
                        self._round_base_n = len(run_info.sv_history)
                    except Exception:
                        self._round_base_n = 0
                    self._win.after(0, self._on_started)

            if self._num_jobs > 1:
                # Successive-jobs pattern (molass-researcher experiment 36) --
                # the library owns the loop + reseed; we just observe each round.
                self._decomp_for_opt.optimize_rigorously(
                    trimmed_ssd=self._trimmed,
                    async_=False,
                    monitor=False,
                    method=method,
                    analysis_folder=self._analysis_folder,
                    pipeline_recipe=pipeline_recipe,
                    num_jobs=self._num_jobs,
                    on_round_start=_on_round_start,
                    stop_check=lambda: self._stopped,
                )
            else:
                run_info = self._decomp_for_opt.optimize_rigorously(
                    trimmed_ssd=self._trimmed,
                    async_=True,
                    monitor=False,
                    method=method,
                    analysis_folder=self._analysis_folder,
                    pipeline_recipe=pipeline_recipe,
                )
                _on_round_start(0, 1, run_info)
        except Exception as exc:
            tb = traceback.format_exc()
            log_path = os.path.join(self._analysis_folder, 'molass_gui_error.log')
            try:
                os.makedirs(self._analysis_folder, exist_ok=True)
                with open(log_path, 'w') as f:
                    f.write(tb)
            except Exception:
                pass
            short = str(exc).split('\n')[0][:120]
            self._win.after(0, lambda m=short: self._status_var.set(
                f"Error: {m}  \u2014 see {log_path}"))

    def _on_started(self):
        self._action_btn.state(['!disabled'])
        self._status_var.set("Running\u2026")
        self._win.after(0, self._watch_tick)
        self._win.after(500, self._ui_poll)

    def _watch_tick(self):
        """Main-thread, self-rescheduling: redraw UV/XR/score panels every ~3 s.

        Must run on the main thread -- matplotlib artists backing a Tk-embedded
        figure are not thread-safe, and mutating them off-thread previously
        crashed the whole process (Tcl_AsyncDelete, molass-gui#1).
        """
        if self._stopped:
            return
        try:
            opt = self._run_info.optimizer
            params = self._run_info.best_params
            if params is None:
                params = self._run_info.init_params
            if params is not None:
                lock = getattr(opt, '_objective_lock', None)
                # Short timeout: this runs on the main thread, so a long wait
                # here would freeze the whole GUI, not just this redraw.
                acquired = lock.acquire(timeout=0.3) if lock else True
                if acquired:
                    try:
                        for ax in (self._ax_uv, self._ax_xr, self._ax_score,
                                   self._ax_xr_twin):
                            ax.cla()
                        self._ax_xr_twin.grid(False)
                        opt.objective_func(params, plot=True,
                                           axis_info=self._axis_info)
                        sv_hist = self._run_info.sv_history
                        # Fall back to the already-known initial score while
                        # sv_history is still empty (run just started, no
                        # accepted trial yet) -- otherwise the SV title
                        # regresses from a known value to blank and then
                        # reappears once the first trial is recorded.
                        sv_now = sv_hist[-1] if sv_hist else getattr(self._score, 'sv', None)
                        _retitle_panels(self._ax_uv, self._ax_xr, self._ax_score, sv_now)
                    finally:
                        if lock:
                            lock.release()
                    self._redraw_event.set()
        except Exception:
            pass
        if not self._stopped:
            self._win.after(3000, self._watch_tick)

    def _ui_poll(self):
        """Main-thread: update labels and flush canvas every 500 ms."""
        if self._stopped:
            return
        if self._run_info is None:
            self._win.after(500, self._ui_poll)
            return
        try:
            status      = self._run_info.live_status()
            phase       = status.get('phase', '?')
            best_sv     = status.get('best_sv')
            n_evals     = status.get('n_evals', 0)
            n_callbacks = status.get('n_callbacks') or 0
            elapsed_s   = status.get('elapsed_s') or 0.0
            manifest    = status.get('manifest') or {}
            niter       = manifest.get('niter', 0)
            n_params    = len(self._run_info.init_params) if self._run_info.init_params is not None else 0
            expected    = _expected_total_units(self._method, niter, n_params)

            self._n_var.set(f"{n_evals} evals")
            if best_sv is not None:
                self._sv_var.set(f"SV: {best_sv:.2f}")
            self._iter_var.set(
                f"Iter: {n_callbacks}/{expected}" if expected else f"Iter: {n_callbacks}")
            self._time_var.set(_fmt_time_info(elapsed_s, n_callbacks, expected))
            if expected:
                # Ceiling for the SV/Rg plots' x-axis: history that existed
                # before this batch started, plus the FULL planned batch
                # (expected-per-round * all num_jobs rounds) -- not just the
                # round in progress, so the already-done portion and the
                # remaining portion are shown to scale (e.g. resuming with as
                # many jobs as already ran should look like ~half done).
                self._niter = self._round_base_n + expected * self._num_jobs

            job_label = f"Job {self._job_round}/{self._num_jobs}"
            if phase == 'failed':
                # live_status() phases are pending/running/completed/failed/unknown
                # (never 'done' -- the previous check here was dead code).
                p = getattr(self._run_info, '_subprocess_process', None)
                rc = p.poll() if p is not None else None
                stderr_path = os.path.join(
                    self._run_info.work_folder or '', 'optimizer_stderr.txt')
                self._status_var.set(
                    f"{job_label}: subprocess error (exit {rc}) \u2014 see {stderr_path}")
                self._stopped = True
                self._show_resumable_controls()
            elif phase == 'completed':
                if self._job_round >= self._num_jobs:
                    self._status_var.set(f"{job_label}: Done.")
                    self._stopped = True
                    self._show_resumable_controls()
                else:
                    self._status_var.set(f"{job_label} complete \u2014 starting next job\u2026")
            else:
                self._status_var.set(f"{job_label}: {phase}")

            try:
                sv_hist = self._run_info.sv_history
                raw_hist = self._run_info.sv_history_raw
                rg_hist = self._run_info.rg_history
                sv_len = len(sv_hist) if sv_hist else 0
                sv_changed = sv_len != self._last_sv_len
                if sv_changed:
                    _draw_sv_history(self._ax_sv, sv_hist, self._niter, raw=raw_hist)
                    _draw_rg_history(self._ax_rg, rg_hist, self._niter)
                    self._last_sv_len = sv_len
            except Exception:
                sv_changed = False
        except Exception:
            sv_changed = False

        if self._redraw_event.is_set() or sv_changed:
            self._redraw_event.clear()
            self._canvas.draw()
        if not self._stopped:
            self._win.after(500, self._ui_poll)

    def _stop(self):
        self._stopped = True
        if self._run_info is not None:
            try:
                self._run_info.stop()
            except Exception:
                pass
        self._status_var.set("Terminating\u2026")
        self._action_btn.state(["disabled"])

        def _wait_dead():
            ri = self._run_info
            if ri is not None:
                for _ in range(60):
                    time.sleep(0.5)
                    if not ri.is_alive:
                        break
            self._win.after(0, self._on_terminated)
        threading.Thread(target=_wait_dead, daemon=True).start()

    def _on_terminated(self):
        # Only reached once the subprocess is confirmed dead (or was never
        # live) -- Resume launches a new subprocess against the same
        # analysis_folder, which must not race a still-live old one.
        self._status_var.set("Terminated.")
        self._show_resumable_controls()


# ------------------------------------------------------------------

def _retitle_panels(ax_uv, ax_xr, ax_score, sv):
    ax_uv.set_title("UV Decomposition", fontsize=16)
    ax_xr.set_title("XR Decomposition", fontsize=16)
    if sv is not None:
        ax_score.set_title(f"Score Breakdown  (SV={sv:.1f})", fontsize=16)
    else:
        ax_score.set_title("Score Breakdown", fontsize=16)


def _fmt_duration(seconds):
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def _expected_total_units(method, niter, n_params):
    """Return the true progress-unit total for the SV-history axis / ETA.

    For BH, `niter` is the hop count -- one callback per hop, 1:1.
    For DE, `niter` is only an input to scipy's fixed evaluation budget;
    the actual number of generations (== callback count) is derived the
    same way SolverDE computes `maxiter` internally, so progress tracks
    the real total instead of the raw `niter` value.
    """
    if method != 'DE' or not niter or not n_params:
        return niter
    try:
        from molass.Solvers.DE.SolverDE import FEVALS_PER_NITER
    except Exception:
        return niter
    actual_popsize = 15 * n_params  # SolverDE default pop_size=15
    return max(1, (niter * FEVALS_PER_NITER) // actual_popsize)


def _fmt_time_info(elapsed_s, n_done, n_total):
    parts = [f"Elapsed: {_fmt_duration(elapsed_s)}"]
    if n_done > 0 and n_total > n_done and elapsed_s > 0:
        rate = elapsed_s / n_done
        remaining = (n_total - n_done) * rate
        parts.append(f"ETA: ~{_fmt_duration(remaining)}")
    return "  ".join(parts)


def _draw_sv_history(ax, sv_hist, niter=0, raw=None):
    ax.cla()
    n = len(sv_hist) if sv_hist else 0
    if raw:
        # scattered dots: every individual trial, including rejected ones --
        # shows the exploration that the flat best-so-far line hides (BH).
        ax.scatter(range(len(raw)), raw, s=6, alpha=0.35, color='darkorange',
                   label='all evals')
    if n > 0:
        xs = range(n)
        ax.step(xs, sv_hist, where='post', lw=1.2, color='steelblue', label='best so far')
        ax.set_ylim(bottom=max(0, min(sv_hist) - 5), top=105)
        if niter > n:
            ax.axvspan(n - 1, niter, alpha=0.06, color='grey')
            ax.axvline(n - 1, color='steelblue', lw=0.8, ls='--', alpha=0.6)
    # niter counts BH hops or DE generations, not evals -- DE evaluates a whole
    # population per generation, so n can overtake niter well before the run
    # is "done". Widen the axis to whichever is larger instead of clipping.
    xlim_max = max(niter, n, len(raw) if raw else 0)
    if xlim_max > 0:
        ax.set_xlim(0, xlim_max)
    ax.set_xlabel("Eval")
    ax.set_ylabel("SV")
    ax.set_title("Function SV")
    if n > 0 or raw:
        ax.legend(loc='lower right', fontsize=7)


def _draw_rg_history(ax, rg_hist, niter=0):
    ax.cla()
    # Rg is a free optimizer parameter (one column per component), so unlike
    # SV there's no "best so far" to accumulate -- just the raw trajectories.
    n = len(rg_hist[0]) if rg_hist and rg_hist[0] else 0
    for k, ys in enumerate(rg_hist or []):
        ax.plot(range(len(ys)), ys, lw=1.0, label=f"Comp {k + 1}")
    xlim_max = max(niter, n)
    if xlim_max > 0:
        ax.set_xlim(0, xlim_max)
    ax.set_xlabel("Eval")
    ax.set_ylabel("Rg")
    ax.set_title("Rg Values")
    if rg_hist:
        ax.legend(loc='upper right', fontsize=7, ncol=min(len(rg_hist), 4))
