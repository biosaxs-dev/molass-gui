<!-- AI Context Standard v0.10.1 - Adopted: 2026-09-30 -->
# AI Assistant Initialization Guide — molass-gui

**Purpose**: Initialize AI context for navigating this repository

> **Note**: For package-consumer-facing content (what this GUI is, the
> five-phase wizard, design philosophy, sharp edges when extending it), see
> [`molass_gui/CONTEXT.md`](../molass_gui/CONTEXT.md) — also shipped inside
> the pip package (`molass_gui.context_path()`), so it's the single source
> of truth for that content; don't duplicate it here.
> For the underlying analysis pipeline, see
> `molass-library/molass/CONTEXT.md`.

---

## Branching Policy

Work happens directly on `main`. No `dev/ongoing-work` or other holding
branches in this repo.

---

## Verification Convention

This repo has **no pytest suite** — Tkinter GUI flows are verified by (a)
live dogfooding (running the actual GUI end-to-end) and (b) small standalone
scripts exercising a specific function/class in isolation (e.g. validating
`build_notebook()`'s output via `nbformat.validate()`, or reproducing a
threading bug with a headless Tk smoke test) rather than a persistent test
file. When fixing a bug here, prefer this same pattern: a throwaway script
that reproduces the issue, not a new permanent test module, unless asked
otherwise.

---

## Multi-Root Workspace Context

This repo is part of the multi-repo VS Code workspace. See
`molass-library/.github/copilot-instructions.md` § "Multi-Root Workspace
Context" for the full ecosystem map.

---

## Response language

**Response language**: English

---

## 🔄 Updates (AI-Readiness Trail)

| Date | What was learned / added |
|------|--------------------------|
| Sep 30, 2026 | Repo adopted the AI Context Standard. Created `molass_gui/CONTEXT.md` (package-shipped, package-consumer-facing) and this file (repo-development-facing) as a pair, following the same split already used in `molass-library`/`molass-legacy`. |
