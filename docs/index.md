# Molass GUI

**Molass GUI** is a point-and-click desktop application for analyzing
SEC-SAXS (size-exclusion chromatography small-angle X-ray scattering) data
— no programming required. It walks you through the same analysis pipeline
as [Molass Library](https://biosaxs-dev.github.io/molass-library), one
window at a time, with live plots at every step.

This site is the GUI's own documentation. If you're looking for the
notebook/API tutorial instead, see
[molass-tutorial](https://biosaxs-dev.github.io/molass-tutorial).

## Get started

1. **[Install](installation.md)** — download, no Python required (Windows)
2. **[Quick Start](quickstart.md)** — your first analysis, step by step, with screenshots

## The five-phase workflow

| Phase | What happens |
|---|---|
| 0. Launcher | Choose New Analysis or Open Existing Analysis |
| 1. Setup | Point at a data folder (or pick a bundled sample dataset) |
| 2. Naive View | Inspect the raw elution curve; decide how many components |
| 3. Quick Optimization View | Review a fast empirical (EGH) decomposition; optionally upgrade to a physics-based column model |
| 4. Upgraded View | Review the upgraded decomposition; launch rigorous optimization |
| 5. Rigorous Optimization View | Watch a live 5-panel monitor as the physically-constrained fit refines |

Every phase also has **Export to Notebook…**, which hands off the exact
pipeline run so far as a real, editable Jupyter notebook — the escape hatch
for anything needing more flexibility than the wizard exposes a button for.

## Getting help

- **Something not working?** [Open an issue](https://github.com/biosaxs-dev/molass-gui/issues/new).
- **Want to understand the science?** See
  [molass-essence](https://biosaxs-dev.github.io/molass-essence) (theory)
  or [molass-technical](https://biosaxs-dev.github.io/molass-technical)
  (technical details).
- **Prefer an AI-guided first run?** See
  [molass-beginner](https://github.com/biosaxs-dev/molass-beginner), an
  Agent-mode onboarding repository.

## License

GNU General Public License v3.0. Source: [github.com/biosaxs-dev/molass-gui](https://github.com/biosaxs-dev/molass-gui).
