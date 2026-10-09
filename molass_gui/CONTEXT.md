# molass-gui — AI assistant context

This file ships **inside the installed package** (`pip install molass-gui`),
so it is current for whatever version you have.

Find this file's absolute path at runtime: `python -c "import molass_gui; print(molass_gui.context_path())"`
(or `molass_gui.print_context()` to dump it directly).

**Read [`molass`'s `CONTEXT.md`](https://github.com/biosaxs-dev/molass-library/blob/main/molass/CONTEXT.md)
first** for the underlying SEC-SAXS analysis pipeline (`SecSaxsData` →
`trimmed_copy` → `quick_decomposition` → `optimize_rigorously`) — this GUI is
a thin Tkinter wizard over exactly that pipeline, not a separate analysis
engine.

---

## What this package is

A Tkinter GUI console-script (`molass-gui`, entry point `molass_gui.launcher:main`)
that walks a user through the same pipeline as `molass`'s tutorial, one phase
at a time, with live plots at each step.

### Five-phase linear wizard

| Phase | Window | What happens |
|---|---|---|
| 0 Launcher | `launcher.py` | Choose **New Analysis** or **Open Existing Analysis** |
| 1 Setup | `app.py` | Enter/pick the data folder |
| 2 Naive View | `naive_view.py` | `plot_compact` with baseline; components spinbox pre-filled via `recommend_decomposition_options()`; **Decompose** |
| 3 Quick Optimization View | `quick_view.py` | Review EGH decomposition; pick a column model; **Upgrade** or **Skip** |
| 4 Upgraded View | `upgraded_view.py` | Review upgraded decomposition; pick method (BH/DE) and subprocess option; **Rigorous Optimization…** |
| 5 Rigorous Optimization View | `rigorous_view.py` | 5-panel live monitor (UV/XR/Score/SV-history/Rg-history); auto-starts; **Terminate**/**Resume** |

Every phase also has **"Continue in Notebook…"**, which exports the exact
pipeline run so far as a real `.ipynb` and opens it — the escape hatch for
anything needing more flexibility than the wizard offers (see design
principle below).

## Design principle: this GUI stays a simple linear wizard, on purpose

There is no Back button and no way to reopen a previous phase's window other
than closing the whole session. This was deliberately reverted from a more
flexible design. If a feature request implies "flexibility" (back
navigation, comparing multiple in-flight runs, re-entrant editing with
tweaked parameters), the answer is **"build it as a notebook workflow
instead"**, not "add a control here" — that's exactly what "Continue in
Notebook…" is for. Don't propose reintroducing window/back-navigation
controls to this GUI without raising this tradeoff explicitly first.

---

## Sharp edges for anyone extending this GUI

### Never touch Tk/matplotlib artifacts from a background thread
Heavy computation (`decomp.score()`, `optimize_rigorously()`, `get_rg_curve()`)
runs on a background thread; anything that draws into a Tk-embedded
`Axes`/canvas, or otherwise mutates Tk widgets, must run on the **main**
thread (via `win.after(...)`), never directly from that background thread.
Violating this crashes the whole process with
`Tcl_AsyncDelete: async handler deleted by the wrong thread` — not a
catchable Python exception, and it kills every window, not just one.

### Always `gc.collect()` after `plt.close()` on an embedded figure
`plot_embed.py`'s `embed_plot()`/`close_dialog_figure()` helpers call
`gc.collect()` immediately after `plt.close(old_fig)` when swapping or
closing an embedded matplotlib figure. matplotlib Figure/Axes/canvas objects
have reference cycles, so `plt.close()` alone doesn't guarantee Tk widget
teardown happens deterministically — without the explicit `gc.collect()`,
teardown can be deferred to whichever thread next triggers a GC pass
(sometimes a background thread), which is the same `Tcl_AsyncDelete` crash
above by a different route. Always use these helpers rather than a bare
`plt.close()` when tearing down an embedded/dialog figure.

### Never `.configure()` a button created before `decomp.score()` runs
Some transitive dependency (`python-tkdnd`/`ttkwidgets`) monkey-patches
`ttk.Widget.configure()` globally as a side effect of `decomp.score()`'s
heavy legacy import. The patch is buggy for widgets that already existed
before it applied, raising `AttributeError`. `.state()`, `.pack()`,
`.pack_forget()`, and creating brand-new widgets are all unaffected. Pattern
used throughout this codebase: pre-create both label/state variants of a
button up front, then swap visibility via `pack()`/`pack_forget()` instead
of calling `.configure()` on it later.

### GUI and notebook-export defaults must agree
Where this GUI pre-fills a value using library logic (e.g. `naive_view.py`'s
components spinbox via `corrected.recommend_decomposition_options()`), the
same logic must be the one actually used, not merely available — a stale
hardcoded default that happens to look similar is a real, previously-shipped
bug class here.

---

## Where to find more

- Design docs: `Copilot/DESIGN_ai_assistant_integration.md`, `Copilot/DESIGN_dropbox_integration.md`, `Copilot/DESIGN_portable_installer.md`
- User documentation (installation, Quick Start walkthrough with screenshots): `docs/` (published at https://biosaxs-dev.github.io/molass-gui/)
- Windows portable zip build: `scripts/build_portable.py` (run via `.github/workflows/build_portable_zip.yml`)
- Main pipeline reference: https://github.com/biosaxs-dev/molass-library (`molass/CONTEXT.md`)
- Source / issues: https://github.com/biosaxs-dev/molass-gui
