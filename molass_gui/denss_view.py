"""Run DENSS dialog -- minimal ab initio electron-density reconstruction on a
single resolved XR component, without any of legacy DenssManager's job-queue/
background-submission/Electron-Density-Viewer machinery.

Component input is always "from memory" (an XrComponent's j-curve array from
the current best rigorous result) -- no file picker, matching the rest of
molass-gui's simple-linear-wizard philosophy.
"""
import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText


def show_denss_lazy(win, status_var, decomp, analysis_folder, rgcurve=None, xr_ranks=None):
    """Load the current best result's XR components and open the Run DENSS dialog."""
    from molass.Rigorous.CurrentStateUtils import load_rigorous_result, list_rigorous_jobs

    prev = status_var.get()
    status_var.set("Loading current result\u2026")
    win.update_idletasks()
    try:
        jobs = list_rigorous_jobs(analysis_folder)
        if not jobs:
            messagebox.showinfo(
                "No results yet",
                "The optimization hasn't produced its first result yet.\n"
                "Try again in a moment.",
                parent=win,
            )
            return
        jobid = min(jobs, key=lambda j: j.best_fv).id
        result = load_rigorous_result(decomp, analysis_folder, jobid=jobid, rgcurve=rgcurve,
                                      xr_ranks=xr_ranks)
    finally:
        status_var.set(prev)

    components = result.get_xr_components()
    DenssDialog(win, components, analysis_folder)


class DenssDialog:
    def __init__(self, parent, components, analysis_folder):
        self._components = components
        self._thread = None
        self._cancel_requested = False
        self._latest = None  # (step, chi2, rg, volume), set by the worker thread
        self._done = False
        self._error = None

        win = tk.Toplevel(parent)
        win.title("Run DENSS")
        self._win = win

        rgs = []
        best_i, best_score = 0, -1
        labels = []
        for i, comp in enumerate(components):
            try:
                sg = comp.get_guinier_object()
                rg, score = sg.Rg, sg.score
            except Exception:
                rg, score = None, 0
            rgs.append(rg)
            if score is not None and score > best_score:
                best_score, best_i = score, i
            labels.append(f"Component {i + 1}  (Rg={rg:.1f} \u00c5)" if rg else f"Component {i + 1}")
        self._rgs = rgs

        sel_frame = ttk.Frame(win, padding=8)
        sel_frame.pack(fill=tk.X)
        ttk.Label(sel_frame, text="Component:").pack(side=tk.LEFT)
        self._comp_var = tk.StringVar(value=labels[best_i])
        self._combo = ttk.Combobox(sel_frame, textvariable=self._comp_var, values=labels,
                                   state="readonly", width=28)
        self._combo.current(best_i)
        self._combo.pack(side=tk.LEFT, padx=8)
        self._combo.bind("<<ComboboxSelected>>", self._on_component_selected)

        ttk.Label(sel_frame, text="Dmax (\u00c5):").pack(side=tk.LEFT, padx=(16, 0))
        init_rg = rgs[best_i] if rgs[best_i] else 30.0
        self._dmax_var = tk.DoubleVar(value=round(init_rg * 3, 1))
        ttk.Entry(sel_frame, textvariable=self._dmax_var, width=8).pack(side=tk.LEFT, padx=8)
        self._dmax_status_var = tk.StringVar(value="")
        ttk.Label(sel_frame, textvariable=self._dmax_status_var, foreground="#666").pack(
            side=tk.LEFT, padx=(4, 0))

        out_frame = ttk.Frame(win, padding=(8, 0))
        out_frame.pack(fill=tk.X)
        ttk.Label(out_frame, text="Output Folder:").pack(side=tk.LEFT)
        default_out = os.path.join(analysis_folder, "DENSS", f"component_{best_i + 1}")
        self._out_var = tk.StringVar(value=default_out)
        ttk.Entry(out_frame, textvariable=self._out_var, width=50).pack(
            side=tk.LEFT, padx=8, fill=tk.X, expand=True)
        ttk.Button(out_frame, text="Browse\u2026", command=self._browse_folder).pack(side=tk.LEFT)

        status_frame = ttk.Frame(win, padding=(8, 8, 8, 0))
        status_frame.pack(fill=tk.X)
        self._status_var = tk.StringVar(value="Ready.")
        self._status_label = ttk.Label(status_frame, textvariable=self._status_var)
        self._status_label.pack(side=tk.LEFT)

        # own row, no sibling widget, so it can stretch across the full dialog width
        pb_frame = ttk.Frame(win, padding=(8, 4, 8, 8))
        pb_frame.pack(fill=tk.X)
        # indeterminate (pulsing) while running -- DENSS stops on chi2
        # convergence, typically far short of MAXNUM_STEPS, so a determinate
        # bar driven by step/MAXNUM_STEPS always looked nearly empty.
        self._pb = ttk.Progressbar(pb_frame, mode="indeterminate")
        self._pb.pack(fill=tk.X, expand=True)

        style = ttk.Style(win)
        style.configure("Done.TLabel", foreground="#16a34a", font=("", 10, "bold"))
        style.configure("Failed.TLabel", foreground="#dc2626", font=("", 10, "bold"))

        log_frame = ttk.Frame(win, padding=8)
        log_frame.pack(fill=tk.BOTH, expand=True)
        self._log_text = ScrolledText(log_frame, width=70, height=12, state="disabled")
        self._log_text.pack(fill=tk.BOTH, expand=True)

        btn_row = ttk.Frame(win, padding=8)
        btn_row.pack()
        self._run_btn = ttk.Button(btn_row, text="Run", command=self._run, style="Accent.TButton")
        self._run_btn.pack(side=tk.LEFT, padx=4)
        self._cancel_btn = ttk.Button(btn_row, text="Cancel", command=self._cancel, state="disabled")
        self._cancel_btn.pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_row, text="Close", command=win.destroy).pack(side=tk.LEFT, padx=4)

        # instant 3xRg guess is shown above already; refine it in the background since the
        # DENSS Dmax estimator can take several seconds (see molass-researcher
        # experiments/39_denss_study/39a_dmax_alpha_estimator.ipynb)
        self._dmax_gen = 0
        self._start_dmax_estimate(best_i)

    def _on_component_selected(self, event=None):
        i = self._combo.current()
        rg = self._rgs[i]
        if rg:
            self._dmax_var.set(round(rg * 3, 1))
        self._start_dmax_estimate(i)

    def _start_dmax_estimate(self, i):
        """Kick off a background DENSS Dmax estimate for component i, refining the instant
        3xRg guess above once it completes. Runs off the UI thread since estimate_dmax can
        take several seconds."""
        self._dmax_gen += 1
        gen = self._dmax_gen
        self._dmax_status_var.set("estimating Dmax\u2026")
        q, a, e = self._components[i].get_jcurve_array().T
        threading.Thread(target=self._dmax_worker, args=(gen, q, a, e), daemon=True).start()

    def _dmax_worker(self, gen, q, a, e):
        import numpy as np
        from molass.SAXS.DmaxEstimation import estimate_dmax
        try:
            mask = (q > 0) & (a > 0)
            Iq = np.vstack((q[mask], a[mask], e[mask])).T
            D, _, _ = estimate_dmax(Iq, clean_up=True)
            result = ("ok", D)
        except Exception as exc:
            result = ("error", exc)
        self._win.after(0, lambda: self._apply_dmax_result(gen, result))

    def _apply_dmax_result(self, gen, result):
        if gen != self._dmax_gen:
            return  # a newer component selection has superseded this estimate
        kind, value = result
        if kind == "ok":
            self._dmax_var.set(round(float(value), 1))
            self._dmax_status_var.set("")
        else:
            self._dmax_status_var.set("auto-estimate failed, using 3\u00d7Rg")

    def _browse_folder(self):
        folder = filedialog.askdirectory(title="Select output folder", parent=self._win)
        if folder:
            self._out_var.set(folder)

    def _run(self):
        i = self._combo.current()
        q, a, e = self._components[i].get_jcurve_array().T
        try:
            dmax = float(self._dmax_var.get())
        except (ValueError, tk.TclError):
            messagebox.showerror("Invalid Dmax", "Dmax must be a number.", parent=self._win)
            return
        out_folder = self._out_var.get()
        if not out_folder:
            messagebox.showerror("Missing output folder", "Please choose an output folder.",
                                 parent=self._win)
            return
        os.makedirs(out_folder, exist_ok=True)

        self._run_btn.state(["disabled"])
        self._combo.state(["disabled"])
        self._cancel_btn.state(["!disabled"])
        self._cancel_requested = False
        self._done = False
        self._error = None
        self._pb.configure(mode="indeterminate")
        self._pb.start(50)
        self._status_label.configure(style="TLabel")
        self._status_var.set("Running\u2026")

        infile_name = f"component_{i + 1}"
        self._thread = threading.Thread(
            target=self._worker, args=(q, a, e, dmax, infile_name, out_folder), daemon=True)
        self._thread.start()
        self._win.after(200, self._poll)

    def _progress_cb(self, step, chi2, rg, volume):
        # runs on the worker thread -- plain attribute assignment only, no Tk calls
        if self._cancel_requested:
            raise RuntimeError("Cancelled by user")
        self._latest = (step, chi2, rg, volume)

    def _worker(self, q, a, e, dmax, infile_name, out_folder):
        cwd = os.getcwd()
        try:
            from molass.SAXS.DenssUtils import run_denss_impl
            os.chdir(out_folder)
            run_denss_impl(q, a, e, dmax, infile_name, progress_cb=self._progress_cb)
        except Exception as exc:
            self._error = exc
        finally:
            os.chdir(cwd)
            self._done = True

    def _poll(self):
        if self._latest is not None:
            step, chi2, rg, volume = self._latest
            self._latest = None
            self._append_log(f"Step {step}: chi2={chi2:.3g} rg={rg:.2f} volume={volume:.0f}\n")
        if self._done:
            self._pb.stop()
            self._run_btn.state(["!disabled"])
            self._combo.state(["!disabled"])
            self._cancel_btn.state(["disabled"])
            if self._error is not None:
                self._pb.configure(mode="determinate", maximum=1, value=0)
                if "Cancelled" in str(self._error):
                    self._status_var.set("\u26a0 Cancelled.")
                    self._append_log("\n----- DENSS cancelled -----\n")
                else:
                    self._status_var.set(f"\u26a0 Error: {self._error}")
                    self._append_log(f"\n----- DENSS failed: {self._error} -----\n")
                self._status_label.configure(style="Failed.TLabel")
            else:
                # fully filled bar, unmistakably "complete" regardless of step count
                self._pb.configure(mode="determinate", maximum=1, value=1)
                self._status_var.set("\u2705 Done.")
                self._append_log("\n===== DENSS run complete =====\n")
                self._status_label.configure(style="Done.TLabel")
            return
        self._win.after(200, self._poll)

    def _append_log(self, text):
        self._log_text.configure(state="normal")
        self._log_text.insert(tk.END, text)
        self._log_text.see(tk.END)
        self._log_text.configure(state="disabled")

    def _cancel(self):
        self._cancel_requested = True
