# molass-gui

Tkinter GUI for [Molass](https://github.com/biosaxs-dev/molass-library) — progressive SEC-SAXS analysis workflow.

## Five-phase workflow

| Phase | Window | What happens |
|---|---|---|
| 1 Setup | Main window | Enter the data folder path |
| 2 Naive View | `plot_compact` with baseline | Inspect raw data; enter number of components; click **Decompose** |
| 3 Quick Optimization View | `plot_components` (EGH) | Review EGH decomposition; select column model; click **Upgrade** or **Skip** |
| 4 Upgraded View | `plot_components` (column model) | Review upgraded decomposition; select method (BH/DE) and subprocess option; click **Rigorous Optimization…** |
| 5 Rigorous Optimization View | 4-panel live monitor | Rg curve computed → initial score drawn → optimization starts automatically; **Terminate** button available |

## Installation

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
- [molass](https://pypi.org/project/molass/) ≥ 1.0.5
- [molass_legacy](https://pypi.org/project/molass_legacy/) ≥ 1.6.13
