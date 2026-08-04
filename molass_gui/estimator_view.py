"""EstimatorView — progress window that runs InitialEstimator.evaluate()."""
import queue
import threading
import tkinter as tk
from tkinter import ttk


class EstimatorView:
    """Progress bar window; calls evaluate() in a thread, then opens ScoreView."""

    def __init__(self, estimator, parent=None):
        self._est = estimator
        self._parent = parent

    def show(self):
        n_frames = len(self._est.decomposition.ssd.xr.jv)
        q = queue.Queue()
        done = threading.Event()
        result_holder = [None]
        error_holder = [None]

        win = tk.Toplevel(self._parent)
        win.title("Computing initial estimate\u2026")
        win.resizable(False, False)
        ttk.Label(win, text="Computing Rg curve\u2026").pack(padx=20, pady=(12, 4))
        pb = ttk.Progressbar(win, maximum=n_frames, length=320)
        pb.pack(padx=20, pady=(0, 12))

        def poll():
            try:
                while True:
                    pb['value'] = q.get_nowait()
            except queue.Empty:
                pass
            if done.is_set():
                win.destroy()
                if error_holder[0] is not None:
                    import tkinter.messagebox as mb
                    mb.showerror("Error", str(error_holder[0]), parent=self._parent)
                else:
                    from molass_gui.score_view import ScoreView
                    ScoreView(result_holder[0], self._est, parent=self._parent).show()
            else:
                win.after(50, poll)     # 20 Hz

        def _progress_cb(rg_buffer, j):
            q.put(j)

        def worker():
            try:
                result_holder[0] = self._est.evaluate(progress_cb=_progress_cb)
            except Exception as exc:
                error_holder[0] = exc
            finally:
                done.set()

        threading.Thread(target=worker, daemon=True).start()
        win.after(50, poll)
