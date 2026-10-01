"""Background Rg-curve computation shared by NaiveView, QuickView and UpgradedView.

Kicks off get_rg_curve() as early as possible rather than waiting until RigorousView's
Phase 5 prep step. get_rg_curve() caches on whatever object computes it -- a corrected
SecSaxsData, or a Decomposition (and its upgrade()'d children via their _parent chain,
which all ultimately defer to that same SecSaxsData's cache) -- so whichever caller
computes it first makes every later caller's get_rg_curve() return instantly.

Decomposition.get_rg_curve() needs no decomposition-specific state: it simply forwards
to self.ssd.get_rg_curve(), which only needs the corrected XR data. So the earliest
possible start is right after SecSaxsData.corrected_copy() succeeds -- well before any
decomposition or its view exists (see NaiveView._detect_worker). start_rgcurve_computation()
is the Tk-free half that can be called at that point; attach_rgcurve_worker() is the
Tk-side half a later view uses to pick up progress/results once it has a status_var/
on_done to drive.

Because this is a CPU-bound, pure-Python per-frame loop, it genuinely competes for the
GIL/CPU with whatever else is running -- harmless while nothing else needs responsiveness
(e.g. while the user is just looking at NaiveView's plot), but visibly slows down a
concurrent CPU-bound caller (e.g. quick_decomposition() and the subsequent view's own
UI/plot build). start_rgcurve_computation()'s optional go_event lets a caller fully
yield this thread for exactly that window, then let it resume.
"""
import queue
import threading


def rgcurve_n_frames(obj):
    """Number of XR frames for *obj* -- a corrected SecSaxsData or a Decomposition."""
    # Decomposition exposes the corrected SecSaxsData as .ssd; a corrected
    # SecSaxsData passed directly (no .ssd of its own) is already that object.
    ssd = getattr(obj, 'ssd', obj)
    return len(ssd.xr.jv)


def start_rgcurve_computation(obj, go_event=None):
    """Compute obj.get_rg_curve() in a background thread, with no Tk dependency.

    *obj* is anything exposing get_rg_curve(progress_cb=...) -- a corrected
    SecSaxsData or a Decomposition. Can be called the instant *obj* is ready,
    independent of any GUI (e.g. right after corrected_copy(), long before a
    Decomposition or its view exist).

    *go_event* (a threading.Event), if given, is waited on after every frame --
    i.e. it must be *set* for the computation to proceed, and *clearing* it
    pauses the computation (blocking, not busy-waiting) until it is set again.
    This is a cooperative, GIL-friendly way to fully yield this (CPU-bound,
    pure-Python per-frame Guinier fit) thread to another caller doing its own
    CPU-heavy work -- e.g. NaiveView clears this during quick_decomposition() +
    QuickView's UI build, since both being CPU-bound at once visibly slows down
    exactly the moment QuickView should appear, then sets it again once
    QuickView is shown. Defaults to always-set behavior (never pauses) if None.

    Returns a queue.Queue carrying ('progress', j), ('done', rgcurve) and
    ('error', str) messages for a later caller to pick up via
    attach_rgcurve_worker(). If the computation finishes before anything
    attaches, the 'done'/'error' message simply waits in the queue.
    """
    q = queue.Queue()

    def _cb(rg_buffer, j):
        q.put(('progress', j))
        if go_event is not None:
            go_event.wait()

    def worker():
        try:
            rgcurve = obj.get_rg_curve(progress_cb=_cb)
            q.put(('done', rgcurve))
        except Exception as exc:
            q.put(('error', str(exc)))

    threading.Thread(target=worker, daemon=True).start()
    return q


def attach_rgcurve_worker(win, q, n_frames, status_var, on_done, progress_cb=None):
    """Attach Tk-side polling to a queue from start_rgcurve_computation().

    Updates *status_var* (if not None) with a "Rg: j/n" progress message while
    running, clears it on completion. Also calls *progress_cb(j, n_frames)*
    (if given) on the Tk main thread each tick -- for callers rendering
    progress some other way (e.g. RigorousView's ttk.Progressbar). Calls
    on_done(rgcurve) on the Tk main thread when finished. On failure, leaves
    an error message in *status_var* (if not None) and does not call on_done.
    """
    if status_var is not None:
        status_var.set(f"Rg: 0/{n_frames}")

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

    win.after(100, poll)


def start_rgcurve_worker(win, decomp, status_var, on_done, progress_cb=None):
    """Compute decomp.get_rg_curve() in a background thread.

    Thin wrapper around start_rgcurve_computation()+attach_rgcurve_worker() for
    callers with no earlier point to get a head start from (e.g. UpgradedView/
    RigorousView, which only ever see *decomp* once it already exists).
    """
    q = start_rgcurve_computation(decomp)
    attach_rgcurve_worker(win, q, rgcurve_n_frames(decomp), status_var, on_done, progress_cb=progress_cb)
