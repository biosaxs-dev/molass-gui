"""OptimizeView — three-panel live monitor for rigorous optimization."""
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk
import numpy as np


class OptimizeView:
    """
    Three-panel live dashboard: UV elution | XR elution | SV history.

    Watch thread acquires optimizer._objective_lock, calls
    objective_func(params, return_lrf_info=True) every ~3 s, puts numpy
    arrays in a queue.  The Tkinter after() poll drains the queue and does
    all matplotlib drawing on the main thread (safe with FigureCanvasTkAgg).
    """

    def __init__(self, score, estimator, analysis_folder, parent=None):
        self._score = score
        self._est = estimator
        self._analysis_folder = analysis_folder
        self._parent = parent
        self._run_info = None
        self._stopped = False
        self._curve_q = queue.Queue(maxsize=1)

    def show(self):
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

        win = tk.Toplevel(self._parent)
        win.title("Rigorous Optimization")

        # Header: status / SV / eval count / Terminate
        hdr = ttk.Frame(win, padding=(8, 4))
        hdr.pack(fill=tk.X)
        self._status_var = tk.StringVar(value="Starting\u2026")
        ttk.Label(hdr, textvariable=self._status_var, width=24).pack(side=tk.LEFT)
        self._sv_var = tk.StringVar(value="SV: \u2014")
        ttk.Label(hdr, textvariable=self._sv_var, font=("", 12, "bold")).pack(
            side=tk.LEFT, padx=16)
        self._n_var = tk.StringVar(value="0 evals")
        ttk.Label(hdr, textvariable=self._n_var).pack(side=tk.LEFT)
        self._stop_btn = ttk.Button(hdr, text="Terminate", command=self._stop,
                                    state="disabled")
        self._stop_btn.pack(side=tk.RIGHT, padx=8)

        # 3-panel figure
        self._fig, axes = plt.subplots(ncols=3, figsize=(18, 4.5))
        self._ax_uv, self._ax_xr, self._ax_sv = axes
        self._ax_xr_twin = self._ax_xr.twinx()
        self._ax_xr_twin.grid(False)

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
            run_info = self._est.decomposition.optimize_rigorously(
                trimmed_ssd=self._est.trimmed_ssd,
                in_process=True,
                async_=True,
                monitor=False,
                analysis_folder=self._analysis_folder,
            )
            self._run_info = run_info
            self._win.after(0, self._on_started)
        except Exception as exc:
            msg = str(exc)
            self._win.after(0, lambda: self._status_var.set(f"Error: {msg}"))

    def _on_started(self):
        self._stop_btn.state(["!disabled"])
        self._status_var.set("Running\u2026")
        threading.Thread(target=self._watch_loop, daemon=True).start()
        self._win.after(500, self._ui_poll)

    def _watch_loop(self):
        """Background: compute curves with lock, put latest in queue."""
        while not self._stopped:
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
                            lrf_info = opt.objective_func(params, return_lrf_info=True)
                        finally:
                            if lock:
                                lock.release()
                        if lrf_info is not None:
                            # read sv_history from disk (fast)
                            sv_hist = self._run_info.sv_history
                            curves = _extract_curves(lrf_info, sv_hist)
                            try:
                                self._curve_q.put_nowait(curves)
                            except queue.Full:
                                pass
            except Exception:
                pass
            time.sleep(3.0)

    def _ui_poll(self):
        """Main-thread: update labels and redraw from latest queue snapshot."""
        if self._run_info is None:
            self._win.after(500, self._ui_poll)
            return
        try:
            status = self._run_info.live_status()
            phase = status.get('phase', '?')
            best_sv = status.get('best_sv')
            n_evals = status.get('n_evals', 0)
            self._n_var.set(f"{n_evals} evals")
            if best_sv is not None:
                self._sv_var.set(f"SV: {best_sv:.2f}")
            if phase == 'done':
                self._status_var.set("Done.")
                self._stop_btn.state(["disabled"])
                self._stopped = True
            else:
                self._status_var.set(f"Phase: {phase}")
        except Exception:
            pass

        # Redraw if watch thread has new data
        try:
            curves = self._curve_q.get_nowait()
            _draw_curves(curves, self._ax_uv, self._ax_xr, self._ax_xr_twin,
                         self._ax_sv)
            self._fig.tight_layout()
            self._canvas.draw()
        except queue.Empty:
            pass

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
        self._stop_btn.state(["disabled"])


# ------------------------------------------------------------------
# Helpers (module-level to keep the class small)
# ------------------------------------------------------------------

def _extract_curves(lrf_info, sv_hist):
    """Pull numpy arrays out of lrf_info."""
    return {
        'xr_frames':     lrf_info.x,
        'xr_data':       lrf_info.y,
        'xr_model':      lrf_info.xr_ty,
        'xr_components': lrf_info.scaled_xr_cy_array,
        'uv_frames':     lrf_info.uv_x,
        'uv_data':       lrf_info.uv_y,
        'uv_model':      lrf_info.uv_ty,
        'uv_components': lrf_info.scaled_uv_cy_array,
        'sv_hist':       sv_hist,
    }


_COLORS = ['tab:blue', 'tab:orange', 'tab:green', 'tab:red', 'tab:purple',
           'tab:brown']


def _draw_curves(c, ax_uv, ax_xr, ax_xr_twin, ax_sv):
    """Draw all three panels from a curves dict.  Called on the main thread."""
    for ax in (ax_uv, ax_xr, ax_xr_twin, ax_sv):
        ax.cla()
    ax_xr_twin.grid(False)

    # --- UV panel ---
    ax_uv.plot(c['uv_frames'], c['uv_data'], color='gray', lw=1.0, label='data')
    ax_uv.plot(c['uv_frames'], c['uv_model'], 'k-', lw=1.5, label='model')
    for k, comp in enumerate(c['uv_components']):
        ax_uv.plot(c['uv_frames'], comp, color=_COLORS[k % len(_COLORS)],
                   lw=1.2, label=f'comp {k+1}')
    ax_uv.set_title('UV elution')
    ax_uv.legend(fontsize=7)

    # --- XR panel ---
    ax_xr.plot(c['xr_frames'], c['xr_data'], color='gray', lw=1.0, label='data')
    ax_xr.plot(c['xr_frames'], c['xr_model'], 'k-', lw=1.5, label='model')
    for k, comp in enumerate(c['xr_components']):
        ax_xr.plot(c['xr_frames'], comp, color=_COLORS[k % len(_COLORS)],
                   lw=1.2, label=f'comp {k+1}')
    ax_xr.set_title('XR elution')
    ax_xr.legend(fontsize=7)

    # --- SV history panel ---
    sv_hist = c.get('sv_hist')
    if sv_hist is not None and len(sv_hist) > 0:
        ax_sv.plot(sv_hist, '-', lw=1.2, color='steelblue')
        ax_sv.set_ylim(bottom=0)
        ax_sv.set_title('SV history')
        ax_sv.set_xlabel('Accepted evaluations')
        ax_sv.set_ylabel('SV')
    else:
        ax_sv.set_title('SV history (waiting\u2026)')

