"""NaiveView — Phase 2: plot_compact + num_components → Decompose → QuickView."""
import threading
import tkinter as tk
from tkinter import ttk


class NaiveView:
    def __init__(self, ssd, trimmed, ctx, parent=None, app_root=None, session_tag=None):
        self._ssd = ssd
        self._trimmed = trimmed
        self._ctx = ctx
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
        ttk.Button(hdr, text="Export to Notebook\u2026",
                  command=self._export_to_notebook).pack(side=tk.RIGHT, padx=8)
        self._status_var = tk.StringVar(value="")
        ttk.Label(hdr, textvariable=self._status_var, foreground="gray").pack(side=tk.LEFT)

        # Show trimmed compact plot with baseline overlay
        result = self._trimmed.plot_compact(baseline=True)
        canvas = FigureCanvasTkAgg(result.fig, master=win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        NavigationToolbar2Tk(canvas, win).update()
        self._win = win

    def _export_to_notebook(self):
        from molass_gui.notebook_export import export_and_open
        export_and_open(self._ctx, self._win)

    def _decompose(self):
        nc = self._nc_var.get()
        self._decomp_btn.state(["disabled"])
        self._status_var.set("Decomposing…")

        def worker():
            try:
                corrected = self._trimmed.corrected_copy()
                # Highly-overlapping peaks (e.g. SAMPLE4) make the default
                # greedy peak-recognition unstable; recommend_decomposition_options()
                # detects this via EGH peeling -- but only at the component count
                # IT finds on its own. Forcing more components than that (e.g. nc=3
                # when auto-detection only distinguishes 2) is itself the unstable
                # case -- SAMPLE4's 3rd component is invisible to auto-detection but
                # still needs proportional slicing, not the greedy default.
                auto_opts = corrected.recommend_decomposition_options()
                auto_nc = auto_opts.get('num_components', nc)
                use_proportions = 'proportions' in auto_opts or nc > auto_nc
                if use_proportions:
                    decomp = corrected.quick_decomposition(num_components=nc, proportions=[1] * nc)
                else:
                    decomp = corrected.quick_decomposition(num_components=nc)

                def on_main():
                    self._decomp_btn.state(["!disabled"])
                    self._status_var.set("Used proportional decomposition (high peak overlap detected)"
                                          if use_proportions else "")
                    self._ctx.num_components = nc
                    self._ctx.use_proportions = use_proportions
                    from molass_gui.quick_view import QuickView
                    QuickView(decomp, self._trimmed, nc, self._ctx, parent=self._win,
                              app_root=self._app_root, session_tag=self._session_tag).show()
                    self._win.withdraw()  # unmap, not just minimize -- iconify() still leaves a taskbar thumbnail

                self._win.after(0, on_main)
            except Exception as exc:
                msg = str(exc)
                def on_error(m=msg):
                    self._status_var.set(f"Error: {m}")
                    self._decomp_btn.state(["!disabled"])
                self._win.after(0, on_error)

        threading.Thread(target=worker, daemon=True).start()
