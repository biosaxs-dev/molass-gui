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

The per-frame loop is CPU-bound pure Python: in a thread it keeps the GIL and makes every
Tk/matplotlib draw of this process ~50x slower for a minute or more (molass-gui#23). So it runs
in a child process (molass-library#400, SecSaxsData.start_rg_curve_process()), which shares
the XR data with this process and writes its running Rg values into shared memory. A small
pump thread (it only sleeps and polls) turns that job into the queue.Queue interface below, so
the views are unchanged. Objects without start_rg_curve_process() (and curves that are already
known or on disk) go through the plain thread, which is then instant or a test double.
"""
import os
import queue
import threading
import time

from molass_gui import busy

PUMP_INTERVAL = 0.1

def rgcurve_n_frames(obj):
    """Number of XR frames for *obj* -- a corrected SecSaxsData or a Decomposition."""
    # Decomposition exposes the corrected SecSaxsData as .ssd; a corrected
    # SecSaxsData passed directly (no .ssd of its own) is already that object.
    ssd = getattr(obj, 'ssd', obj)
    return len(ssd.xr.jv)


def _process_target(obj):
    """The SecSaxsData whose Rg curve should be computed in a child process, or None for the plain thread:
    objects that cannot do it, and curves already known or on disk (loading them is instant)."""
    ssd = getattr(obj, 'ssd', obj)
    if not hasattr(ssd, 'start_rg_curve_process'):
        return None
    if getattr(obj, 'has_rg_curve', False):
        return None
    cache_path = getattr(obj, '_rg_curve_cache_path', None)
    if cache_path is not None and os.path.isfile(cache_path):
        return None
    return ssd


def start_rgcurve_computation(obj):
    """Compute obj.get_rg_curve() in the background, with no Tk dependency.

    *obj* is anything exposing get_rg_curve(progress_cb=...) -- a corrected
    SecSaxsData or a Decomposition. Can be called the instant *obj* is ready,
    independent of any GUI (e.g. right after corrected_copy(), long before a
    Decomposition or its view exist). The computation runs in a child process
    (see the module docstring), so it does not compete with the GUI for the GIL.

    Returns a queue.Queue carrying ('progress', j), ('done', rgcurve) and
    ('error', str) messages for a later caller to pick up via
    attach_rgcurve_worker(). If the computation finishes before anything
    attaches, the 'done'/'error' message simply waits in the queue.
    The queue's ``stop`` attribute (a threading.Event) cancels the computation
    when set -- see stop_rgcurve_computation().
    """
    q = queue.Queue()
    q.stop = threading.Event()

    ssd = _process_target(obj)
    job = None
    if ssd is not None:
        try:
            job = ssd.start_rg_curve_process()
        except Exception:
            job = None      # no child process possible here: the slow thread beats no curve

    if job is not None:
        threading.Thread(target=_pump, args=(job, q, obj, ssd), daemon=True).start()
        return q

    def _cb(rg_buffer, j):
        q.put(('progress', j))

    def worker():
        try:
            rgcurve = obj.get_rg_curve(progress_cb=_cb)
            q.put(('done', rgcurve))
        except Exception as exc:
            q.put(('error', str(exc)))

    threading.Thread(target=worker, daemon=True).start()
    return q


def _pump(job, q, obj, ssd):
    """Turn the RgCurveJob into the queue messages: it only sleeps and polls, so it costs the GUI nothing."""
    last = 0
    try:
        while True:
            if q.stop.is_set():
                job.cancel()
                return
            outcome = job.poll()
            n_done, _ = job.progress()
            if n_done > last:
                last = n_done
                q.put(('progress', n_done - 1))
            if outcome is None:
                time.sleep(PUMP_INTERVAL)
                continue
            kind, payload = outcome
            if kind == 'done':
                rgcurve = payload
                if obj is not ssd:
                    try:
                        rgcurve = obj.get_rg_curve()    # cached by now; also fills a decomposition's own cache file
                    except Exception:
                        pass
                q.put(('done', rgcurve))
            elif kind == 'error':
                q.put(('error', payload.splitlines()[0] if payload else 'the Rg-curve process failed'))
            return
    except Exception as exc:
        job.close()
        q.put(('error', str(exc) or type(exc).__name__))


def stop_rgcurve_computation(q):
    """Cancel the computation behind a queue from start_rgcurve_computation() (a no-op for the plain
    thread, which cannot be stopped, and for one that is already finished)."""
    stop = getattr(q, 'stop', None)
    if stop is not None:
        stop.set()


def attach_rgcurve_worker(win, q, n_frames, status_var, on_done, progress_cb=None):
    """Attach Tk-side polling to a queue from start_rgcurve_computation().

    Shows a "Computing the Rg curve... j/n" busy message in *status_var* (if not None) while
    running (see busy.py), clears it on completion. Also calls *progress_cb(j, n_frames)*
    (if given) on the Tk main thread each tick -- for callers rendering
    progress some other way (e.g. RigorousView's ttk.Progressbar). Calls
    on_done(rgcurve) on the Tk main thread when finished. On failure, leaves
    an error message in *status_var* (if not None) and does not call on_done.
    """
    token = busy.begin(win, status_var, f"Computing the Rg curve\u2026 0/{n_frames}") if status_var is not None else None

    def poll():
        # the view was left by its Back button: stop, and leave the queue to the next view of this decomposition
        if not win.winfo_exists():
            return
        while True:
            try:
                kind, payload = q.get_nowait()
            except queue.Empty:
                break
            if kind == 'progress':
                if token is not None:
                    token.update(f"Computing the Rg curve\u2026 {payload}/{n_frames}")
                if progress_cb is not None:
                    progress_cb(payload, n_frames)
            elif kind == 'done':
                if token is not None:
                    token.end(status="")
                on_done(payload)
                return
            elif kind == 'error':
                if token is not None:
                    token.end(status=f"Rg curve failed: {payload}")
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
