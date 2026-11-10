"""NaiveView — Phase 2: plot_compact + num_components → Decompose → QuickView."""
import threading
import tkinter as tk
from tkinter import ttk

import numpy as np
from matplotlib.legend import Legend
from matplotlib.lines import Line2D

from molass_gui.peak_selection import (parse_positions, format_positions, classify_peaks, default_selection,
                                       toggle_peak)
from molass_gui.trimming_info import fmt_qrange, fmt_interparticle_hint

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
        # Filled in by _detect_worker (background thread kicked off from show()) --
        # cached and reused by _decompose so the GUI's own default matches exactly
        # what recommend_decomposition() would do, and so it's never recomputed twice.
        self._corrected = None
        self._auto_opts = None
        # Queue for the Rg-curve computation kicked off by _detect_worker as soon as
        # self._corrected exists -- forwarded to QuickView so it attaches to this
        # already-running computation instead of starting its own, later one.
        self._rgcurve_queue = None
        # threading.Event.wait() blocks while *clear* and returns immediately while
        # *set* -- so this is a "go ahead" flag: set (the default) means the Rg-curve
        # background computation may proceed; _decompose() clears it to pause that
        # computation for its own CPU-bound quick_decomposition() + QuickView UI-build
        # window (both being CPU-bound at once otherwise visibly delays QuickView's
        # appearance), then sets it again once QuickView is shown (or on error) to
        # let the Rg curve resume toward completion.
        self._rgcurve_go = threading.Event()
        self._rgcurve_go.set()

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
        # Placeholder until _detect_worker fills in the recommended value below --
        # disabled in the meantime so a user can't decompose against the stale guess.
        self._nc_var = tk.IntVar(value=1)
        self._nc_spinbox = ttk.Spinbox(hdr, from_=1, to=10, textvariable=self._nc_var, width=5)
        self._nc_spinbox.pack(side=tk.LEFT, padx=6)
        ttk.Label(hdr, text="Proportions (optional):").pack(side=tk.LEFT, padx=(12, 0))
        self._proportions_var = tk.StringVar(value="")
        self._proportions_var.trace_add("write", self._sync_nc_from_proportions)
        ttk.Entry(hdr, textvariable=self._proportions_var, width=18).pack(
            side=tk.LEFT, padx=6)
        # proportions_source only affects the proportions path (see molass-library
        # quick_decomposition's proportions_source kwarg) -- hidden (not just disabled)
        # until proportions is non-empty, shown/hidden by _sync_nc_from_proportions.
        self._proportions_source_var = tk.BooleanVar(value=False)  # False='xr' (default), True='uv'
        self._on_uv_check = ttk.Checkbutton(hdr, text="on UV", variable=self._proportions_source_var)
        self._decomp_btn = ttk.Button(hdr, text="Decompose", command=self._decompose,
                                     style="Accent.TButton")
        self._decomp_btn.pack(side=tk.LEFT, padx=12)
        ttk.Button(hdr, text="Export to Notebook\u2026",
                  command=self._export_to_notebook).pack(side=tk.RIGHT, padx=8)
        self._status_var = tk.StringVar(value="Detecting components\u2026")
        ttk.Label(hdr, textvariable=self._status_var, foreground="gray").pack(side=tk.LEFT)
        self._nc_spinbox.state(["disabled"])
        self._decomp_btn.state(["disabled"])

        # Peak positions (molass-gui#14): the user's own choice of the XR peak frames, an alternative to
        # Proportions. Two modes: off (the initial one, no peak marks, as before this feature; the field is empty
        # so the default decomposition is unchanged) and on (marks shown, clicking the curve selects peaks).
        self._peak_mode = False
        hdr2 = ttk.Frame(win, padding=(8, 0))
        hdr2.pack(fill=tk.X)
        ttk.Label(hdr2, text="Peak positions (optional):").pack(side=tk.LEFT)
        self._peaks_var = tk.StringVar(value="")
        self._peaks_var.trace_add("write", self._on_peaks_changed)
        self._peaks_entry = ttk.Entry(hdr2, textvariable=self._peaks_var, width=28, state="disabled")
        self._peaks_entry.pack(side=tk.LEFT, padx=6)
        self._peak_btn = ttk.Button(hdr2, text="Show confirmed peaks", command=self._start_peak_selection)
        self._peak_btn.pack(side=tk.LEFT, padx=6)
        self._peak_btn.state(["disabled"])   # until the detection has finished
        ttk.Button(hdr2, text="Clear", command=self._clear_peak_selection).pack(side=tk.LEFT)
        self._peak_hint_var = tk.StringVar(value="")
        ttk.Label(hdr2, textvariable=self._peak_hint_var, foreground="#555").pack(side=tk.LEFT, padx=12)

        # the angular range the trimming kept (molass-library#342): read-only, so the default is visible
        self._range_var = tk.StringVar(value=fmt_qrange(self._ssd, self._trimmed))
        ttk.Label(win, textvariable=self._range_var, foreground="#555", padding=(8, 0)).pack(anchor=tk.W)

        # Show trimmed compact plot with baseline overlay
        result = self._trimmed.plot_compact(baseline=True)
        canvas = FigureCanvasTkAgg(result.fig, master=win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self._toolbar = NavigationToolbar2Tk(canvas, win)
        self._toolbar.update()
        self._win = win
        self._canvas = canvas
        self._xr_ax = result.axes[0]
        x, y = result.xr_curve.get_xy()
        self._xr_x, self._xr_y = np.asarray(x), np.asarray(y)
        self._marker_artists = []
        self._candidates = []      # [(frame, confirmed)] from the detection
        self._confirmed_default = []
        canvas.mpl_connect("button_press_event", self._on_curve_click)

        threading.Thread(target=self._detect_worker, daemon=True).start()

    def _detect_worker(self):
        # Runs once per session (result cached in self._corrected/self._auto_opts and
        # reused by _decompose) -- same auto-detection recommend_decomposition() uses,
        # so the GUI's own default reproduces exactly what the notebook equivalent would
        # do instead of an arbitrary fixed guess.
        try:
            corrected = self._trimmed.corrected_copy()
            # Earliest possible start for the Rg curve: get_rg_curve() needs only the
            # corrected XR data, nothing decomposition-specific (it's cached on this
            # same `corrected` object and inherited unchanged by decomp/decomp.upgrade()
            # later -- see rgcurve_worker.py). Kick it off here, in parallel with
            # auto-detection below and with however long the user takes to click
            # Decompose, instead of waiting for a Decomposition/QuickView to exist.
            # go_event: _decompose() clears this to pause for its own CPU-bound window.
            from molass_gui.rgcurve_worker import start_rgcurve_computation
            rgcurve_queue = start_rgcurve_computation(corrected, go_event=self._rgcurve_go)
            auto_opts = corrected.recommend_decomposition_options()
        except Exception as exc:
            msg = str(exc)
            def on_error(m=msg):
                self._status_var.set(f"Auto-detect failed ({m}) -- using manual default")
                self._nc_var.set(3)
                self._nc_spinbox.state(["!disabled"])
                self._decomp_btn.state(["!disabled"])
            self._win.after(0, on_error)
            return

        # The peaks the XR/UV mapping confirms, to tell them from the merely detected ones in the plot.
        # Optional: without it (e.g. no UV data) every detected peak is shown as unconfirmed.
        try:
            confirmed = [int(p) for p in corrected.estimate_mapping().xr_peaks]
        except Exception:
            confirmed = None
        detected = [int(p) for p in auto_opts.get('xr_peakpositions', [])]   # an ndarray: no `or []`

        def on_main():
            self._corrected = corrected
            self._rgcurve_queue = rgcurve_queue
            self._auto_opts = auto_opts
            self._nc_var.set(auto_opts.get('num_components', 1))
            self._candidates = classify_peaks(detected, confirmed)
            self._confirmed_default = default_selection(detected, confirmed)
            if self._confirmed_default:
                self._peak_btn.state(["!disabled"])
            # shown in the status label: the rank-2 (interparticle) case is rare
            self._status_var.set(fmt_interparticle_hint(auto_opts))
            self._nc_spinbox.state(["!disabled"])
            self._decomp_btn.state(["!disabled"])

        self._win.after(0, on_main)

    def _export_to_notebook(self):
        from molass_gui.notebook_export import export_and_open
        export_and_open(self._ctx, self._win)

    # --- Peak positions (molass-gui#14) ---

    def _frame_range(self):
        return (self._xr_x[0], self._xr_x[-1])

    def _current_positions(self):
        """The chosen peak frames, [] when the field is empty, None while the text does not parse."""
        try:
            return parse_positions(self._peaks_var.get(), self._frame_range())
        except ValueError:
            return None

    def _on_peaks_changed(self, *_args):
        # Like Proportions, a chosen set of peaks fixes the number of components: reflect it live.
        positions = self._current_positions()
        if positions:
            self._nc_var.set(len(positions))
        self._redraw_peak_markers()

    def _start_peak_selection(self):
        """Off -> on: show the peak marks and pre-select the confirmed peaks, to be adjusted by clicking."""
        self._peak_mode = True
        self._peaks_entry.state(["!disabled"])
        self._peak_btn.configure(text="Use selected peaks")
        self._peak_btn.state(["disabled"])   # a label: Decompose uses the selection
        self._peak_hint_var.set("click the curve to add/remove a peak")
        self._peaks_var.set(format_positions(self._confirmed_default))
        self._redraw_peak_markers()

    def _clear_peak_selection(self):
        """On -> off: clear the field and go back to the initial state, with no peak marks."""
        self._peak_mode = False
        self._peaks_var.set("")
        self._peaks_entry.state(["disabled"])
        self._peak_btn.configure(text="Show confirmed peaks")
        if self._confirmed_default:
            self._peak_btn.state(["!disabled"])
        self._peak_hint_var.set("")
        self._redraw_peak_markers()

    def _on_curve_click(self, event):
        if not self._peak_mode:
            return
        # The XR panel has a twin (UV) y-axis on top of it, so event.inaxes is that twin, never self._xr_ax:
        # test the panel's area instead and convert the pixel to a frame on the XR axis.
        if event.x is None or event.y is None or not self._xr_ax.bbox.contains(event.x, event.y):
            return
        if self._toolbar.mode != "":
            return  # zoom/pan is active
        frame = self._xr_ax.transData.inverted().transform((event.x, event.y))[0]
        positions = self._current_positions()
        if positions is None:
            return
        new = toggle_peak(positions, frame, self._xr_x, self._xr_y, candidates=[f for f, _ in self._candidates])
        if new != positions:
            self._peaks_var.set(format_positions(new))

    def _redraw_peak_markers(self):
        for artist in self._marker_artists:
            artist.remove()
        self._marker_artists = []
        if self._peak_mode:
            self._draw_peak_markers()
        self._canvas.draw_idle()

    def _draw_peak_markers(self):
        ax = self._xr_ax
        xlim, ylim = ax.get_xlim(), ax.get_ylim()
        ymax = float(np.nanmax(self._xr_y)) if len(self._xr_y) else 1.0
        for frame, confirmed in self._candidates:
            i = int(np.argmin(np.abs(self._xr_x - frame)))
            y = float(self._xr_y[i])
            self._marker_artists.append(ax.plot(
                [frame], [y + 0.03*ymax], marker="v", markersize=8, linestyle="none", color="tab:red",
                markerfacecolor="tab:red" if confirmed else "none", zorder=5)[0])
        for frame in self._current_positions() or []:
            self._marker_artists.append(ax.axvline(frame, color="tab:green", linestyle="--", linewidth=1.2, zorder=4))
            self._marker_artists.append(ax.annotate(
                str(frame), (frame, ylim[1]), xytext=(2, -12), textcoords="offset points", color="tab:green",
                fontsize=8, annotation_clip=False))
        ax.set_xlim(xlim)
        ax.set_ylim(ylim)
        legend = Legend(ax, [
            Line2D([], [], marker="v", markersize=8, linestyle="none", color="tab:red"),
            Line2D([], [], marker="v", markersize=8, linestyle="none", color="tab:red", markerfacecolor="none"),
            Line2D([], [], color="tab:green", linestyle="--", linewidth=1.2)],
            ["seen in XR and UV", "seen in XR only", "selected"], loc="upper right", fontsize=8)
        # added as an artist, so the plot's own legend is left alone
        self._marker_artists.append(ax.add_artist(legend))

    def _sync_nc_from_proportions(self, *_args):
        # Custom proportions supersedes Components -- reflect its length live,
        # so the two fields can never silently disagree. Ignored while the
        # text doesn't yet parse (e.g. mid-edit, trailing comma) rather than
        # showing an error on every keystroke.
        text = self._proportions_var.get().strip()
        # before= pins the checkbox's position regardless of pack() call order --
        # it's shown/hidden repeatedly as the user types, so relying on call order
        # alone would drift it to the end of the LEFT stack after the first toggle.
        if text:
            self._on_uv_check.pack(side=tk.LEFT, padx=(0, 6), before=self._decomp_btn)
        else:
            self._on_uv_check.pack_forget()
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

        # Peak positions is an alternative to Proportions, not a complement: both fix where the
        # components sit, so giving both is ambiguous.
        peak_positions = self._current_positions()
        if peak_positions is None:
            try:
                parse_positions(self._peaks_var.get(), self._frame_range())
            except ValueError as exc:
                self._status_var.set(f"Error: {exc}")
            return
        if peak_positions and custom_proportions is not None:
            self._status_var.set("Error: give either Peak positions or Proportions, not both")
            return

        # Proportions is authoritative when given -- Components is kept in sync
        # live by _sync_nc_from_proportions, but re-derive here too so a
        # mismatch can never actually occur regardless of widget-event timing.
        if custom_proportions is not None:
            nc = len(custom_proportions)
        elif peak_positions:
            nc = len(peak_positions)
        else:
            nc = self._nc_var.get()
        self._nc_var.set(nc)

        self._decomp_btn.state(["disabled"])
        self._status_var.set("Decomposing…")
        # Pause the (possibly still-running) Rg-curve computation for this whole
        # CPU-bound window -- quick_decomposition() below and QuickView's UI build
        # in on_main are both CPU-bound too, and a background thread contending for
        # the GIL at the same time visibly delays QuickView's appearance. Set again
        # once QuickView is actually shown (or on error), letting it resume.
        self._rgcurve_go.clear()

        def worker():
            try:
                # Reuse the detection kicked off by show() -- same corrected data and
                # recommendation, computed once per session instead of on every click.
                corrected = self._corrected
                if custom_proportions is not None:
                    proportions = custom_proportions
                    trust_proportions = True
                elif peak_positions:
                    proportions = None
                    trust_proportions = True   # the user's own positions, not a patch: default constraint weight
                else:
                    # Highly-overlapping peaks (e.g. SAMPLE4) make the default
                    # greedy peak-recognition unstable; recommend_decomposition_options()
                    # detects this via EGH peeling -- but only at the component count
                    # IT finds on its own. Forcing more components than that (e.g. nc=3
                    # when auto-detection only distinguishes 2) is itself the unstable
                    # case -- SAMPLE4's 3rd component is invisible to auto-detection but
                    # still needs proportional slicing, not the greedy default.
                    auto_opts = self._auto_opts
                    auto_nc = auto_opts.get('num_components', nc)
                    needs_fallback = 'proportions' in auto_opts or nc > auto_nc
                    proportions = [1] * nc if needs_fallback else None
                    # This equal split is a patch for the peeling algorithm's own
                    # shortfall, not a choice the user made -- must not silently pose
                    # as a validated, precisely-known position. But that doesn't mean
                    # no constraint should apply: loosen it instead of disabling it
                    # (molass-gui#3) so gross collapse/drift is still blocked.
                    trust_proportions = not needs_fallback

                # on-UV checkbox only ever applies to a user-typed proportions list --
                # not the equal-split fallback, which is already flagged untrusted below.
                proportions_source = ('uv' if proportions is not None and custom_proportions is not None
                                       and self._proportions_source_var.get() else None)
                if proportions is not None:
                    extra = {'proportions_source': proportions_source} if proportions_source else {}
                    decomp = corrected.quick_decomposition(num_components=nc, proportions=proportions, **extra)
                elif peak_positions:
                    decomp = corrected.quick_decomposition(num_components=nc, xr_peakpositions=peak_positions)
                else:
                    decomp = corrected.quick_decomposition(num_components=nc)

                def on_main():
                    self._decomp_btn.state(["!disabled"])
                    self._status_var.set("Used proportional decomposition" if proportions is not None
                                          else f"Used peak positions {format_positions(peak_positions)}"
                                          if peak_positions else "")
                    self._ctx.num_components = nc
                    self._ctx.proportions = proportions
                    self._ctx.xr_peakpositions = peak_positions or None
                    self._ctx.proportions_source = proportions_source
                    self._ctx.trust_proportions = trust_proportions
                    self._ctx.constraint_weight = None if trust_proportions else FALLBACK_LUMPING_WEIGHT
                    from molass_gui.quick_view import QuickView
                    QuickView(decomp, self._trimmed, nc, self._ctx, parent=self._win,
                              app_root=self._app_root, session_tag=self._session_tag,
                              rgcurve_queue=self._rgcurve_queue).show()
                    self._win.withdraw()  # unmap, not just minimize -- iconify() still leaves a taskbar thumbnail
                    self._rgcurve_go.set()  # resume the Rg curve now that QuickView is up

                self._win.after(0, on_main)
            except Exception as exc:
                msg = str(exc)
                def on_error(m=msg):
                    from molass_gui.error_dialog import show_error_detail
                    show_error_detail(self._win, self._status_var, m, title="Decomposition failed")
                    self._decomp_btn.state(["!disabled"])
                    self._rgcurve_go.set()  # don't leave the Rg curve stuck paused on failure
                self._win.after(0, on_error)

        threading.Thread(target=worker, daemon=True).start()
