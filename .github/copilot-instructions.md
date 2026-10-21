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

## Git and shell quirks on Windows PowerShell

Shared rules from [ai-context-standard](https://github.com/freesemt/ai-context-standard) v0.10.2 ("PowerShell Terminal — Native-command Output and Commit Messages"):

- A red `NativeCommandError` after `git push` / `fetch` or `gh` is stderr progress, not failure. Judge by the result line (`a1b2c3d..e4f5a6b  main -> main`, `✓ Closed issue`) or `git status -sb`; do not retry.
- Commit messages (and `gh ... --body-file` text): write to a fresh file with the editor's create tool, then `git commit -F <file>`. `git commit -F -` from a here-string fails. Keep trailers such as `Co-authored-by:`.
- `| Select-Object -Last N` buffers output until the command ends; silence is expected.
- Tool calls in one batch run in parallel: read an artifact in a later batch than the call that creates it.

## Response language

**Response language**: English

---

## 🔄 Updates (AI-Readiness Trail)

| Date | What was learned / added |
|------|--------------------------|
| Sep 30, 2026 | Repo adopted the AI Context Standard. Created `molass_gui/CONTEXT.md` (package-shipped, package-consumer-facing) and this file (repo-development-facing) as a pair, following the same split already used in `molass-library`/`molass-legacy`. |
