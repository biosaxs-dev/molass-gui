# Design: Windows Portable Installer

**Status**: Implemented (2026-10-09). See "Final design" below for what shipped.

**Context**: Opened directly in service of the JAC Computer Programs article's
two-independent-user and public-availability requirements (see
`molass-papers/upgraded-molass/OUTLINE.md` §6/§7) — a beginner SAXS scientist
with no Python background needs a way to actually run the GUI before either
requirement is realistically satisfiable. `pip install molass-gui` is fine
for Python users but a real barrier otherwise.

---

## Final design

A self-contained `molass-gui-<version>-portable-win64.zip`, built by
`scripts/build_portable.py` and attached to GitHub Releases by
`.github/workflows/build_portable_zip.yml`. Unzip, double-click
`molass-gui.bat` — no installer, no admin rights, no existing Python, fully
offline after the one download.

### Why this shape, not the alternatives

Considered and rejected, discussed with the author first:

- **PyInstaller + Inno Setup**: the author had previously moved away from
  PyInstaller specifically (reason not fully diagnosed, described as
  "including unnecessary [things]") — ruled out at the author's direction
  before implementation started, not re-litigated here.
- **`uv`-based on-first-run fetching**: tiny initial download, but requires
  internet access on first launch — ruled out because beamline/instrument-
  control PCs are often on restricted or air-gapped networks, which this
  audience specifically includes.
- **Pre-baked portable distro (WinPython etc.)**: the one genuinely hard
  part (Tcl/Tk bundling, below) is already solved here directly; a generic
  bundle would add unrelated bulk (Jupyter, an IDE, etc.) for no benefit.
- **MSIX/Nuitka/conda-pack**: new toolchains this project doesn't otherwise
  use, weaker Tkinter/numba/scikit-learn track record (Nuitka) or worse
  first-run trust friction for this audience (MSIX side-loading) than
  unzip-and-run.

### Mechanism

1. Download the official python.org *embeddable* package (pinned version,
   not scraped — see `PYTHON_VERSION` in `build_portable.py`).
2. Bootstrap pip (`get-pip.py`), `pip install molass-gui --only-binary=:all:`.
   Confirmed (2026-10-09) every dependency — numpy/scipy/scikit-learn/numba/
   pandas/matplotlib/lmfit etc. — has an official Windows wheel for the
   pinned Python version, so this needs no compiler.
3. Bundle Tcl/Tk (see below) and a trimmed `molass_data` sample (see below).
4. Write a `.bat` launcher, zip the result.

### Tcl/Tk bundling (the one genuinely hard part)

The embeddable package deliberately ships no Tcl/Tk/tkinter at all. Fixed by
copying `_tkinter.pyd`, `tcl86t.dll`, `tk86t.dll`, the `tcl/`/`Lib/tkinter`
trees, **and `zlib1.dll`**, from a same-version regular Python install —
the DLL layout (`.\DLLs\` subfolder + `_pth` edit) mirrors
`molass-legacy/molass_legacy/Build/Embeddables.py`'s own `copy_tkinter()`,
chosen because that convention has already survived several Python version
bumps in this codebase. `zlib1.dll` is the easy-to-miss one: undocumented,
but `_tkinter.pyd` fails to load without it from Python 3.12 onward —
already known to `Embeddables.py` (its own comment names exactly this
fact), independently rediscovered here the hard way (a `DLL load failed`
error) before that prior art was found.

`Embeddables.py`'s *other* machinery — dynamic "scrape python.org for the
latest version," the Gohlke-fallback dispatch for packages lacking
wheels — was deliberately **not** ported: both solve problems that no
longer exist now that every dependency ships an official wheel.

### Local-source installs need a wheel pre-build step

`--only-binary=:all:` (needed so pip never tries to compile anything inside
the embeddable env) breaks installing a local source checkout directly: pip
then can't fetch `hatchling`, molass-gui's own build backend, failing with
`BackendUnavailable: Cannot import 'hatchling.build'`. Fixed by building the
wheel with the *host's* own unrestricted pip first
(`resolve_install_target()`), then installing only that already-built wheel
into the embeddable env.

### Bundled sample data: SAMPLE1 only

`naive_view.py`'s Sample dropdown (`_discover_samples()`) only appears if
`molass_data` is importable — without it, a first-time user has no data to
try the [Quick Start guide](../docs/quickstart.md) with. Bundling all five
samples would nearly double the zip (~120 MB vs. the ~270 MB base); `SAMPLE1`
alone is ~13 MB and is also the dataset both this guide's screenshots and
`molass-tutorial`'s own Quick Start use. `bundle_sample_data()` installs the
real `molass_data` wheel (so it stays a real, version-tracked, upgradable
dependency) and then deletes `SAMPLE2`–`SAMPLE5`'s folders and their
`__init__.py` assignments post-install — not a hand-copied subset — so the
dropdown only ever offers what's actually present.

### Known cosmetic-only issue

`Expand-Archive` (PowerShell's built-in unzip) is unusably slow on this
many-small-files archive (confirmed: tens of minutes), apparently worse
under real-time antivirus scanning. Not a code issue — `docs/installation.md`
tells users to expect the first extraction to take a few minutes and to use
Windows' native "Extract All" (or 7-Zip), not a PowerShell one-liner.

### Build-environment note (not a code issue, recorded for future debugging)

While developing the screenshot-capture harness that produced
`docs/quickstart.md`'s screenshots, a 5+ minute stall traced back to
unrelated, legitimate, concurrently-running `molass-gui --dropbox-support`
optimization subprocesses on this shared development machine, not to
anything in this installer or the GUI itself. Mentioned here only so a
future "why is this suddenly slow" investigation checks for CPU contention
from other processes before assuming a regression.
