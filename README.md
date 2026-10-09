# molass-gui

Tkinter GUI for [Molass](https://github.com/biosaxs-dev/molass-library) — progressive SEC-SAXS analysis workflow.

📖 **New here? See the [Quick Start guide with screenshots](https://biosaxs-dev.github.io/molass-gui/quickstart)**
(no Python required — [Windows portable download](https://biosaxs-dev.github.io/molass-gui/installation), no installer, no admin rights).

## Five-phase workflow

| Phase | Window | What happens |
|---|---|---|
| 1 Setup | Main window | Enter the data folder path |
| 2 Naive View | `plot_compact` with baseline | Inspect raw data; enter number of components; click **Decompose** |
| 3 Quick Optimization View | `plot_components` (EGH) | Review EGH decomposition; select column model; click **Upgrade** or **Skip** |
| 4 Upgraded View | `plot_components` (column model) | Review upgraded decomposition; select method (BH/DE) and subprocess option; click **Rigorous Optimization…** |
| 5 Rigorous Optimization View | 4-panel live monitor | Rg curve computed → initial score drawn → optimization starts automatically; **Terminate** button available |

## Installation

**No Python?** Download the Windows portable zip from the
[latest Release](https://github.com/biosaxs-dev/molass-gui/releases/latest)
— unzip and double-click `molass-gui.bat`. See the
[installation guide](https://biosaxs-dev.github.io/molass-gui/installation) for details.

**Have Python 3.9–3.14?**

```
pip install molass-gui
```

## Usage

```
molass-gui
```

Or during development (from the repository root):

```
py app.py
```

## Requirements

- Python 3.9–3.14
- [molass](https://pypi.org/project/molass/) ≥ 1.0.7
- [molass_legacy](https://pypi.org/project/molass_legacy/) ≥ 1.6.15
