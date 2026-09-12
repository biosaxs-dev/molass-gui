# Design: Dropbox Integration for molass-gui

**Status**: Discussion — not yet implemented. Resume here.

**Context**: `molass-library` (main repo) now provides `molass.DataUtils.sync_dropbox_folder`
(module: `molass/DataUtils/DropboxSync.py`), which caches a Dropbox folder locally via
the Dropbox API (bulk zip download, per-file fallback for large folders), avoiding the
repeated re-downloads that happen when reading directly from a Dropbox-desktop-synced
"Online-only" folder. It was prototyped in `molass-researcher/shared/` and promoted to
`molass-library` on 2026-09-12. Credentials: env vars or `~/.molass/dropbox_credentials.json`.
`start_authorize()`/`finish_authorize()`/`save_credentials()` are split into separate
steps specifically so a GUI can drive the OAuth flow with its own dialogs instead of a
blocking console `input()`.

This doc captures the discussion on how `molass-gui` should surface this feature.

---

## 1. Where the entry point lives

`molass_gui/app.py`'s `App._build_ui()` (Phase 1, "New Analysis") already has: Data
folder Entry + "Browse…" button + Sample dropdown + Recent dropdown, all feeding one
`self._folder_var` → `_run()`. Natural fit: add a **"From Dropbox…"** button next to
"Browse…" that opens a small dialog, and on success just sets `self._folder_var` to the
returned local cache path (existing `_run()` flow handles the rest unchanged).

## 2. The one-time OAuth "connect" flow — no "Settings" concept exists yet

`molass-gui` currently has zero settings/account screens (deliberately —
`recent_folders.py`'s docstring explicitly avoids molass-legacy's `Settings`
singleton). Two options:

- **Inline/connect-on-demand** (leaning this way): the "From Dropbox…" dialog checks
  `load_credentials()`; if it raises, show a small "Connect to Dropbox" step (App Key
  entry → "Open Browser" button via `webbrowser.open()` → paste-code Entry → "Connect")
  right there, then proceed to the path entry. No new app-level concept introduced.
- **Dedicated Account/Settings screen**: first-class, reusable, but this app has never
  had one — bigger structural addition than the feature itself really needs right now.

## 3. Copy-paste code vs. fully automatic redirect

`start_authorize()`/`finish_authorize()` already implement the PKCE **no-redirect**
flow (user pastes a code back manually — one extra step, no local server). A fully
automatic flow would need `DropboxOAuth2Flow` (not `FlowNoRedirect`) plus a tiny local
HTTP listener running temporarily inside the Tk app to catch the browser redirect —
more moving parts (a local port, a background thread) for a one-time setup step.
**Leaning**: start with paste-code; only build the local-listener version if that step
proves annoying in practice.

## 4. Should `dropbox` be a hard dependency of molass-gui?

In `molass-library` it's optional (`pip install molass[dropbox]`) since most library
users don't need it. But `molass-gui`'s whole point is being the friendly on-ramp — a
"From Dropbox…" button that's silently broken unless you separately installed an extra
is bad UX. **Leaning**: make `molass-gui`'s `pyproject.toml` depend on
`molass[dropbox]>=1.0.9` directly, so it's always available in the GUI.

## 5. Progress feedback needs a callback, not `print()`

`sync_folder()` currently reports progress via `print()` — invisible in a GUI.
`app.py`'s `_run()` already has the thread + `.after(0, ...)` pattern for safe UI
updates from a background thread. **Leaning**: add an optional
`on_status: Callable[[str], None]` param to `molass.DataUtils.sync_dropbox_folder`
(small, backward-compatible **molass-library** change) so the GUI can route
"Downloading…"/"Up to date" text into its status label instead of stdout.

## 6. Recent Dropbox paths

`molass_gui/recent_folders.py` already takes a `kind` parameter — a `kind="dropbox"`
list (`~/.molass-gui/recent_folders_dropbox.json`) reuses it with zero new code in
that module.

---

## Open question for next session

Confirm (or adjust) the "leaning" choices in points 2–4 above, then implement:

1. `molass-library`: add `on_status` callback param to `sync_folder()`.
2. `molass-gui`: new `molass_gui/dropbox_dialog.py` (or similar) with the connect +
   path-entry flow, wired into `app.py`'s `_build_ui()`.
3. `molass-gui/pyproject.toml`: `molass[dropbox]>=1.0.9`.
4. Manual test: fresh machine (no credentials) → connect flow → sync → Load → NaiveView.
