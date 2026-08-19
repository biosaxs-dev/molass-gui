"""NaiveView — Phase 2: plot_compact + num_components → Decompose → QuickView."""
import threading
import tkinter as tk
from tkinter import ttk


class NaiveView:
    def __init__(self, ssd, trimmed, parent=None, app_root=None, session_tag=None):
        self._ssd = ssd
        self._trimmed = trimmed
        self._parent = parent
        self._app_root = app_root
        self._session_tag = session_tag

    def show(self):
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

        win = tk.Toplevel(self._parent)
        title = "Naive View"
        if self._session_tag:
            title += f"  [{self._session_tag}]"
        win.title(title)
        win.protocol("WM_DELETE_WINDOW", self._app_root.close_session)

        # Header: num_components + Decompose button + status
        hdr = ttk.Frame(win, padding=(8, 4))
        hdr.pack(fill=tk.X)
        ttk.Label(hdr, text="Components:").pack(side=tk.LEFT)
        self._nc_var = tk.IntVar(value=3)
        ttk.Spinbox(hdr, from_=1, to=6, textvariable=self._nc_var, width=5).pack(
            side=tk.LEFT, padx=6)
        self._decomp_btn = ttk.Button(hdr, text="Decompose", command=self._decompose,
                                     style="Accent.TButton")
        self._decomp_btn.pack(side=tk.LEFT, padx=12)
        self._status_var = tk.StringVar(value="")
        ttk.Label(hdr, textvariable=self._status_var, foreground="gray").pack(side=tk.LEFT)

        # Show trimmed compact plot with baseline overlay
        result = self._trimmed.plot_compact(baseline=True)
        canvas = FigureCanvasTkAgg(result.fig, master=win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        NavigationToolbar2Tk(canvas, win).update()
        self._win = win

    def _decompose(self):
        nc = self._nc_var.get()
        self._decomp_btn.state(["disabled"])
        self._status_var.set("Decomposing\u2026")

        def worker():
            try:
                corrected = self._trimmed.corrected_copy()
                decomp = corrected.quick_decomposition(num_components=nc)

                def on_main():
                    self._decomp_btn.state(["!disabled"])
                    self._status_var.set("")
                    from molass_gui.quick_view import QuickView
                    QuickView(decomp, self._trimmed, nc, parent=self._win,
                              app_root=self._app_root, session_tag=self._session_tag).show()
                    self._win.iconify()

                self._win.after(0, on_main)
            except Exception as exc:
                msg = str(exc)
                def on_error(m=msg):
                    self._status_var.set(f"Error: {m}")
                    self._decomp_btn.state(["!disabled"])
                self._win.after(0, on_error)

        threading.Thread(target=worker, daemon=True).start()
