"""OptimizeView — four-panel live monitor for rigorous optimization."""
import os
import sys
import traceback
import threading
import time
import tkinter as tk
from tkinter import ttk


class OptimizeView:
    """
    Four-panel live dashboard:
      Top row:    UV elution | XR elution | Score breakdown
      Bottom row: SV history (full width)

    Watch thread acquires optimizer._objective_lock, calls
    objective_func(params, plot=True) every ~3 s to draw UV/XR/score panels,
    then draws SV history.  Sets _redraw_event; main thread calls canvas.draw().
    """

    def __init__(self, score, estimator, analysis_folder, parent=None):
        self._score = score
        self._est = estimator
        self._analysis_folder = analysis_folder
        self._parent = parent
        self._run_info = None
        self._stopped = False
        self._niter = 0
        self._redraw_event = threading.Event()

    def show(self):
        import matplotlib.pyplot as plt
        import matplotlib.gridspec as gridspec
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

        win = tk.Toplevel(self._parent)
        win.title("Rigorous Optimization")

        # Header
        hdr = ttk.Frame(win, padding=(8, 4))
        hdr.pack(fill=tk.X)
        self._status_var = tk.StringVar(value="Starting\u2026")
        ttk.Label(hdr, textvariable=self._status_var, width=24).pack(side=tk.LEFT)
        self._sv_var = tk.StringVar(value="SV: \u2014")
        ttk.Label(hdr, textvariable=self._sv_var, font=("", 12, "bold")).pack(
            side=tk.LEFT, padx=16)
        self._n_var = tk.StringVar(value="0 evals")
        ttk.Label(hdr, textvariable=self._n_var).pack(side=tk.LEFT)
        self._iter_var = tk.StringVar(value="Iter: —")
        ttk.Label(hdr, textvariable=self._iter_var).pack(side=tk.LEFT, padx=12)
        self._time_var = tk.StringVar(value="")
        ttk.Label(hdr, textvariable=self._time_var, foreground="#555").pack(
            side=tk.LEFT, padx=4)
        self._stop_btn = ttk.Button(hdr, text="Terminate", command=self._stop,
                                    state="disabled")
        self._stop_btn.pack(side=tk.RIGHT, padx=8)

        # Figure: top 3 panels + bottom SV strip
        self._fig = plt.figure(figsize=(18, 6.5))
        gs = gridspec.GridSpec(2, 3, figure=self._fig,
                               height_ratios=[4, 1.5], hspace=0.45)
        self._ax_uv    = self._fig.add_subplot(gs[0, 0])
        self._ax_xr    = self._fig.add_subplot(gs[0, 1])
        self._ax_score = self._fig.add_subplot(gs[0, 2])
        self._ax_xr_twin = self._ax_xr.twinx()
        self._ax_xr_twin.grid(False)
        self._ax_sv    = self._fig.add_subplot(gs[1, :])   # full-width SV strip
        self._axis_info = (self._fig,
                           (self._ax_uv, self._ax_xr, self._ax_score, self._ax_xr_twin))

        # Draw initial state (init_params) synchronously on the main thread
        # so panels are never blank when the window first appears.
        try:
            opt0 = self._score.optimizer
            opt0.objective_func(
                self._score.init_params, plot=True, axis_info=self._axis_info)
            _retitle_panels(self._ax_uv, self._ax_xr, self._ax_score, self._score.sv)
            _draw_sv_history(self._ax_sv, [], 0)
        except Exception:
            pass

        canvas = FigureCanvasTkAgg(self._fig, master=win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        NavigationToolbar2Tk(canvas, win).update()
        self._canvas = canvas

        self._win = win
        threading.Thread(target=self._launch, daemon=True).start()

    # ------------------------------------------------------------------

    def _launch(self):
        try:
            use_subprocess = getattr(self._est, '_use_subprocess', False)
            pipeline_recipe = getattr(self._est, '_pipeline_recipe', None)
            
            run_info = self._est.decomposition.optimize_rigorously(
                trimmed_ssd=self._est.trimmed_ssd,
                in_process=not use_subprocess,  # Inverted: checkbox=True → subprocess mode
                async_=True,
                monitor=False,
                analysis_folder=self._analysis_folder,
                pipeline_recipe=pipeline_recipe,
            )
            self._run_info = run_info
            self._win.after(0, self._on_started)
        except Exception as exc:
            tb = traceback.format_exc()
            # Always write full traceback to a log file next to the analysis folder.
            log_path = os.path.join(self._analysis_folder, 'molass_gui_error.log')
            try:
                os.makedirs(self._analysis_folder, exist_ok=True)
                with open(log_path, 'w') as _f:
                    _f.write(tb)
            except Exception:
                pass
            print(tb, file=sys.stderr)
            short = str(exc).split('\n')[0][:120]
            self._win.after(0, lambda: self._status_var.set(
                f"Error: {short}  — see {log_path}"))

    def _on_started(self):
        self._stop_btn.state(["!disabled"])
        self._status_var.set("Running\u2026")
        threading.Thread(target=self._watch_loop, daemon=True).start()
        self._win.after(500, self._ui_poll)

    def _watch_loop(self):
        """Background: draw UV/XR/score panels via objective_func every ~3 s."""
        first = True
        while not self._stopped:
            if first:
                first = False
            else:
                time.sleep(3.0)
            try:
                opt = self._run_info.optimizer
                params = self._run_info.best_params
                if params is None:
                    params = self._run_info.init_params
                if params is not None:
                    lock = getattr(opt, '_objective_lock', None)
                    acquired = lock.acquire(timeout=1.5) if lock else True
                    if acquired:
                        try:
                            for ax in (self._ax_uv, self._ax_xr, self._ax_score,
                                       self._ax_xr_twin):
                                ax.cla()
                            self._ax_xr_twin.grid(False)
                            opt.objective_func(params, plot=True,
                                               axis_info=self._axis_info)
                            sv_hist = self._run_info.sv_history
                            sv_now = sv_hist[-1] if sv_hist else None
                            _retitle_panels(self._ax_uv, self._ax_xr, self._ax_score, sv_now)
                        finally:
                            if lock:
                                lock.release()
                        self._redraw_event.set()
            except Exception:
                pass

    def _ui_poll(self):
        """Main-thread: update labels; flush canvas when watch thread is done."""
        if self._stopped:
            return
        if self._run_info is None:
            self._win.after(500, self._ui_poll)
            return
        try:
            status = self._run_info.live_status()
            phase      = status.get('phase', '?')
            best_sv    = status.get('best_sv')
            n_evals    = status.get('n_evals', 0)
            n_callbacks = status.get('n_callbacks') or 0
            elapsed_s  = status.get('elapsed_s') or 0.0
            manifest   = status.get('manifest') or {}
            niter      = manifest.get('niter', 0)

            self._n_var.set(f"{n_evals} evals")
            if best_sv is not None:
                self._sv_var.set(f"SV: {best_sv:.2f}")
            self._iter_var.set(
                f"Iter: {n_callbacks}/{niter}" if niter else f"Iter: {n_callbacks}")
            self._time_var.set(_fmt_time_info(elapsed_s, n_callbacks, niter))
            if niter:
                self._niter = niter

            if phase == 'done':
                self._status_var.set("Done.")
                self._stop_btn.state(["disabled"])
                self._stopped = True
            else:
                # Detect subprocess crash: process dead but no callback data.
                p = getattr(self._run_info, '_subprocess_process', None)
                if p is not None and p.poll() is not None and p.poll() != 0 and not n_callbacks:
                    stderr_path = os.path.join(
                        self._run_info.work_folder or '', 'optimizer_stderr.txt')
                    self._status_var.set(
                        f"Subprocess error (exit {p.poll()}) — see {stderr_path}")
                    self._stop_btn.state(["disabled"])
                    self._stopped = True
                else:
                    self._status_var.set(f"Phase: {phase}")

            # SV strip drawn every tick regardless of watch_loop status.
            try:
                sv_hist = self._run_info.sv_history
                _draw_sv_history(self._ax_sv, sv_hist, self._niter)
            except Exception:
                pass
        except Exception:
            pass

        # TODO perf: skip draw when sv_hist length unchanged and _redraw_event not set.
        # TODO perf: use canvas.blit(ax_sv.bbox) for SV strip instead of full canvas.draw().
        self._redraw_event.clear()
        self._canvas.draw()

        if not self._stopped:
            self._win.after(500, self._ui_poll)

    def _stop(self):
        self._stopped = True
        if self._run_info is not None:
            try:
                self._run_info.request_stop()      # in_process=True: cooperative stop
            except Exception:
                pass
            try:
                p = getattr(self._run_info, '_subprocess_process', None)
                if p is not None:
                    p.terminate()                  # subprocess mode: SIGTERM
            except Exception:
                pass
        self._status_var.set("Terminating\u2026")
        self._stop_btn.state(["disabled"])
        # Poll until process exits, then show Terminated.
        def _wait_dead():
            ri = self._run_info
            if ri is not None:
                for _ in range(60):   # up to 30 s
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


def _fmt_time_info(elapsed_s, n_done, n_total):
    parts = [f"Elapsed: {_fmt_duration(elapsed_s)}"]
    if n_done > 0 and n_total > 0 and elapsed_s > 0:
        rate = elapsed_s / n_done          # seconds per BH hop
        remaining = (n_total - n_done) * rate
        parts.append(f"ETA: ~{_fmt_duration(remaining)}")
    return "  ".join(parts)


def _draw_sv_history(ax, sv_hist, niter=0):
    ax.cla()
    n = len(sv_hist) if sv_hist else 0
    if n > 0:
        xs = range(n)
        ax.step(xs, sv_hist, where='post', lw=1.2, color='steelblue')
        ax.set_ylim(bottom=max(0, min(sv_hist) - 5), top=105)
        # shade the remaining region
        if niter > n:
            ax.axvspan(n - 1, niter, alpha=0.06, color='grey')
            ax.axvline(n - 1, color='steelblue', lw=0.8, ls='--', alpha=0.6)
    if niter > 0:
        ax.set_xlim(0, niter)
    ax.set_xlabel("BH hop")
    ax.set_ylabel("SV")
    ax.set_title("SV history")
