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
from molass_gui.window_tree import register_window_cleanup, register_close_guard


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
            Keys: use_subprocess, pipeline_recipe.
        analysis_folder : str
            Output folder for optimization results.
        ctx : SessionContext or None
            Accumulated GUI choices, for "Continue in Notebook…".
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
        self._method = 'BH'
        self._last_sv_len = 0
        self._redraw_event = threading.Event()

    def show(self):
        import matplotlib.pyplot as plt
        import matplotlib.gridspec as gridspec
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

        win = tk.Toplevel(self._parent)
        recipe = (self._est_kwargs.get('pipeline_recipe') or {})
        model  = recipe.get('model', 'egh').upper()
        method = recipe.get('method', 'bh').upper()
        self._method = method
        proc   = 'subprocess' if self._est_kwargs.get('use_subprocess') else 'in-process'
        title = f"Rigorous Optimization — {model} | {method} | {proc}"
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
        self._prep_var = tk.StringVar(value="Computing Rg curve\u2026")
        ttk.Label(self._prep_frame, textvariable=self._prep_var).pack(side=tk.LEFT)
        n_frames = len(self._decomp.ssd.xr.jv)
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
        self._action_btn = ttk.Button(hdr, text="Terminate", command=self._stop,
                                      state='disabled', style="Danger.TButton")
        self._action_btn.pack(side=tk.RIGHT, padx=8)
        self._params_btn = ttk.Button(hdr, text="Show Parameters\u2026",
                                      command=self._show_parameters, state="disabled")
        self._params_btn.pack(side=tk.RIGHT, padx=8)
        if self._ctx is not None:
            ttk.Button(hdr, text="Continue in Notebook\u2026",
                      command=self._continue_in_notebook).pack(side=tk.RIGHT, padx=8)
        if self._score is not None:
            self._params_btn.state(["!disabled"])

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

        self._win.after(10, self._prep_main)

    # ------------------------------------------------------------------
    # Prep phase

    def _prep_main(self):
        """Main-thread: compute Rg curve (usually instant -- cached by QuickView/
        UpgradedView) then build the optimizer via score().

        Runs synchronously on the main thread rather than a background thread.
        score()'s construction path goes through legacy code whose thread-safety
        with the active Tk/matplotlib backend is not guaranteed; running it off
        the main thread previously crashed the whole process (Tcl_AsyncDelete,
        molass-gui#1) even after get_rg_curve() itself was confirmed cached.
        """
        try:
            def _rg_cb(rg_buffer, j):
                self._pb['value'] = j
                self._win.update_idletasks()
            self._decomp.get_rg_curve(progress_cb=_rg_cb)
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
        self._optimize()  # auto-start; user can Terminate if needed

    def _show_parameters(self):
        # run_info.best_params reflects the live/final run once one exists;
        # falls back to the initial score's params before/without a run.
        params = None
        if self._run_info is not None:
            params = self._run_info.best_params
        show_parameters_lazy(self, self._win, self._status_var, self._decomp_for_opt,
                             self._trimmed, params=params)

    def _continue_in_notebook(self):
        from molass_gui.notebook_export import export_and_open
        export_and_open(self._ctx, self._win)

    # ------------------------------------------------------------------
    # Optimization phase

    def _optimize(self):
        self._status_var.set("Starting\u2026")
        threading.Thread(target=self._launch, daemon=True).start()

    def _launch(self):
        try:
            use_subprocess  = self._est_kwargs.get('use_subprocess', False)
            pipeline_recipe = self._est_kwargs.get('pipeline_recipe', None)
            method = (pipeline_recipe or {}).get('method', 'BH').upper()

            run_info = self._decomp_for_opt.optimize_rigorously(
                trimmed_ssd=self._trimmed,
                in_process=not use_subprocess,
                async_=True,
                monitor=False,
                method=method,
                analysis_folder=self._analysis_folder,
                pipeline_recipe=pipeline_recipe,
            )
            self._run_info = run_info
            self._win.after(0, self._on_started)
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
                self._niter = expected

            if phase == 'done':
                self._status_var.set("Done.")
                self._action_btn.state(["disabled"])
                self._stopped = True
            else:
                p = getattr(self._run_info, '_subprocess_process', None)
                if p is not None and p.poll() is not None and p.poll() != 0 and not n_callbacks:
                    stderr_path = os.path.join(
                        self._run_info.work_folder or '', 'optimizer_stderr.txt')
                    self._status_var.set(
                        f"Subprocess error (exit {p.poll()}) \u2014 see {stderr_path}")
                    self._action_btn.state(["disabled"])
                    self._stopped = True
                else:
                    self._status_var.set(f"Phase: {phase}")

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
            self._win.after(0, lambda: self._status_var.set("Terminated."))
        threading.Thread(target=_wait_dead, daemon=True).start()


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
