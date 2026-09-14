"""NaiveView — Phase 2: plot_compact + num_components → Decompose → QuickView."""
import threading
import tkinter as tk
from tkinter import ttk

# LumpingConstraint's own default (0.2) is calibrated for confident,
# independently-detected peak positions. When the equal-split fallback fires,
# a component's "position" is just the centroid of an arbitrary equal-area
# cut (see molass-library/molass/Decompose/Proportional.py) -- not a real
# detection. This weight is loose enough to not penalize legitimate
# refinement near that unconfirmed default, while still blocking gross
# (500+ frame) drift/collapse. See molass-gui#3.
FALLBACK_LUMPING_WEIGHT = 0.01


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
        ttk.Spinbox(hdr, from_=1, to=10, textvariable=self._nc_var, width=5).pack(
            side=tk.LEFT, padx=6)
        ttk.Label(hdr, text="Proportions (optional):").pack(side=tk.LEFT, padx=(12, 0))
        self._proportions_var = tk.StringVar(value="")
        self._proportions_var.trace_add("write", self._sync_nc_from_proportions)
        ttk.Entry(hdr, textvariable=self._proportions_var, width=18).pack(
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

    def _sync_nc_from_proportions(self, *_args):
        # Custom proportions supersedes Components -- reflect its length live,
        # so the two fields can never silently disagree. Ignored while the
        # text doesn't yet parse (e.g. mid-edit, trailing comma) rather than
        # showing an error on every keystroke.
        text = self._proportions_var.get().strip()
        if not text:
            return
        try:
            values = [float(s) for s in text.split(",")]
        except ValueError:
            return
        if values:
            self._nc_var.set(len(values))

    def _decompose(self):
        custom_text = self._proportions_var.get().strip()
        custom_proportions = None
        if custom_text:
            try:
                custom_proportions = [float(s) for s in custom_text.split(",")]
            except ValueError:
                self._status_var.set("Error: proportions must be comma-separated numbers")
                return

        # Proportions is authoritative when given -- Components is kept in sync
        # live by _sync_nc_from_proportions, but re-derive here too so a
        # mismatch can never actually occur regardless of widget-event timing.
        nc = len(custom_proportions) if custom_proportions is not None else self._nc_var.get()
        self._nc_var.set(nc)

        self._decomp_btn.state(["disabled"])
        self._status_var.set("Decomposing…")

        def worker():
            try:
                corrected = self._trimmed.corrected_copy()
                if custom_proportions is not None:
                    proportions = custom_proportions
                    trust_proportions = True
                else:
                    # Highly-overlapping peaks (e.g. SAMPLE4) make the default
                    # greedy peak-recognition unstable; recommend_decomposition_options()
                    # detects this via EGH peeling -- but only at the component count
                    # IT finds on its own. Forcing more components than that (e.g. nc=3
                    # when auto-detection only distinguishes 2) is itself the unstable
                    # case -- SAMPLE4's 3rd component is invisible to auto-detection but
                    # still needs proportional slicing, not the greedy default.
                    auto_opts = corrected.recommend_decomposition_options()
                    auto_nc = auto_opts.get('num_components', nc)
                    needs_fallback = 'proportions' in auto_opts or nc > auto_nc
                    proportions = [1] * nc if needs_fallback else None
                    # This equal split is a patch for the peeling algorithm's own
                    # shortfall, not a choice the user made -- must not silently pose
                    # as a validated, precisely-known position. But that doesn't mean
                    # no constraint should apply: loosen it instead of disabling it
                    # (molass-gui#3) so gross collapse/drift is still blocked.
                    trust_proportions = not needs_fallback

                if proportions is not None:
                    decomp = corrected.quick_decomposition(num_components=nc, proportions=proportions)
                else:
                    decomp = corrected.quick_decomposition(num_components=nc)

                def on_main():
                    self._decomp_btn.state(["!disabled"])
                    self._status_var.set("Used proportional decomposition"
                                          if proportions is not None else "")
                    self._ctx.num_components = nc
                    self._ctx.proportions = proportions
                    self._ctx.trust_proportions = trust_proportions
                    self._ctx.constraint_weight = None if trust_proportions else FALLBACK_LUMPING_WEIGHT
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
