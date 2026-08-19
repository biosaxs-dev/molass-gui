"""Background Rg-curve computation shared by QuickView and UpgradedView.

Kicks off decomp.get_rg_curve() as early as possible (right when its view opens) rather
than waiting until RigorousView's Phase 5 prep step -- Decomposition.get_rg_curve() caches
on the decomp (and on upgrade()'d children via their _parent chain), so whichever view
computes it first makes every later view's call return instantly.
"""
import queue
import threading


def start_rgcurve_worker(win, decomp, status_var, on_done):
    """Compute decomp.get_rg_curve() in a background thread.

    Updates *status_var* with a "Rg: j/n" progress message while running, clears it on
    completion, then calls on_done(rgcurve) on the Tk main thread. On failure, leaves an
    error message in *status_var* and does not call on_done.
    """
    q = queue.Queue()
    n_frames = len(decomp.ssd.xr.jv)
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
                status_var.set(f"Rg: {payload}/{n_frames}")
            elif kind == 'done':
                status_var.set("")
                on_done(payload)
                return
            elif kind == 'error':
                status_var.set(f"Rg error: {payload}")
                return
        win.after(100, poll)

    threading.Thread(target=worker, daemon=True).start()
    win.after(100, poll)
