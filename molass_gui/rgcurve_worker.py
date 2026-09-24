"""Background Rg-curve computation shared by QuickView and UpgradedView.

Kicks off decomp.get_rg_curve() as early as possible (right when its view opens) rather
than waiting until RigorousView's Phase 5 prep step -- Decomposition.get_rg_curve() caches
on the decomp (and on upgrade()'d children via their _parent chain), so whichever view
computes it first makes every later view's call return instantly.
"""
import queue
import threading


def start_rgcurve_worker(win, decomp, status_var, on_done, progress_cb=None):
    """Compute decomp.get_rg_curve() in a background thread.

    Updates *status_var* (if not None) with a "Rg: j/n" progress message while
    running, clears it on completion. Also calls *progress_cb(j, n_frames)*
    (if given) on the Tk main thread each tick -- for callers rendering
    progress some other way (e.g. RigorousView's ttk.Progressbar). Calls
    on_done(rgcurve) on the Tk main thread when finished. On failure, leaves
    an error message in *status_var* (if not None) and does not call on_done.
    """
    q = queue.Queue()
    n_frames = len(decomp.ssd.xr.jv)
    if status_var is not None:
        status_var.set(f"Rg: 0/{n_frames}")

    def worker():
        def _cb(rg_buffer, j):
            q.put(('progress', j))
        try:
            rgcurve = decomp.get_rg_curve(progress_cb=_cb)
            q.put(('done', rgcurve))
        except Exception as exc:
            q.put(('error', str(exc)))

    def poll():
        while True:
            try:
                kind, payload = q.get_nowait()
            except queue.Empty:
                break
            if kind == 'progress':
                if status_var is not None:
                    status_var.set(f"Rg: {payload}/{n_frames}")
                if progress_cb is not None:
                    progress_cb(payload, n_frames)
            elif kind == 'done':
                if status_var is not None:
                    status_var.set("")
                on_done(payload)
                return
            elif kind == 'error':
                if status_var is not None:
                    status_var.set(f"Rg error: {payload}")
                return
        win.after(100, poll)

    threading.Thread(target=worker, daemon=True).start()
    win.after(100, poll)
