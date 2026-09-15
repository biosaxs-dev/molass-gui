# Design: Dropbox Integration for molass-gui

**Status**: Implemented (2026-09-13). See "Final design" below for what shipped.

**Context**: `molass-library` (main repo) provides `molass.DataUtils.sync_dropbox_folder`
(module: `molass/DataUtils/DropboxSync.py`), which caches a Dropbox folder locally via
the Dropbox API (bulk zip download, per-file fallback for large folders), avoiding the
repeated re-downloads that happen when reading directly from a Dropbox-desktop-synced
"Online-only" folder. It was prototyped in `molass-researcher/shared/` and promoted to
`molass-library` on 2026-09-12. Credentials: env vars or `~/.molass/dropbox_credentials.json`.
`start_authorize()`/`finish_authorize()`/`save_credentials()` are split into separate
steps specifically so a GUI can drive the OAuth flow with its own dialogs instead of a
blocking console `input()`.

---

## Final design (superseding the discussion below)

No new "From Dropbox…" button, no dedicated dialog, no new pyproject dependency.
Dropbox handling is fully implicit, detected only from the folder path the user
already provided via the existing "Browse…"/typed/Recent flow:

- **Trigger**: in `App._run()`, `"dropbox" in folder.lower()` (case-insensitive
  substring on the path) — a heuristic, not a hard rule; refine later if needed
  (e.g. custom-named Dropbox Business folders won't match).
- **Path conversion**: `App._to_dropbox_path()` finds the path segment containing
  "dropbox" and returns everything after it, `/`-joined, as the Dropbox-API-relative
  path (e.g. `C:\Users\me\Dropbox\MOLASS\Data\X` → `/MOLASS/Data/X`).
- **Credentials missing**: `App._connect_dropbox_dialog()` — a small blocking modal
  (App Key → "Open Browser…" → paste code → "Connect") shown only at this point, using
  `DropboxSync.start_authorize/finish_authorize/save_credentials`. Cancelling aborts
  the load. `dropbox` package not installed → warn once, then proceed with the local
  path unchanged (no hard dependency added).
- **Sync + progress**: done inside the existing background worker thread; `on_status`
  callback (new `molass-library` param) routes progress text into the existing
  `self._status_var` label via the existing `.after(0, ...)` pattern — no new UI.
- **Fallback on failure**: any exception from path resolution or `sync_dropbox_folder`
  (false-positive match, wrong derived path, API error) falls back to using the
  original local path directly, with a one-line status warning — never blocks the load.
- **Recent/session identity**: `recent_folders.add(...)` and `SessionContext(...)`
  still use the *original* folder path (not the resolved local cache path), so re-runs
  re-trigger the same detection+sync logic and outputs stay colocated with the user's
  real Dropbox-synced folder.
- **Exported notebook** (`notebook_export.py`): must also resolve via
  `sync_dropbox_folder`, not embed the raw local path -- otherwise re-running the
  exported notebook reads directly from the online-only Dropbox folder again,
  defeating the entire feature. `session_context.to_dropbox_path()` (the same
  heuristic, extracted to a shared function) is exposed as `ctx.dropbox_path`;
  `build_notebook()` generates a `sync_dropbox_folder(...)` cell when set. Bonus:
  this makes the exported notebook portable across machines (Dropbox-relative path,
  not a machine-specific local mount path).

Implementation: `molass_gui/session_context.py` (`to_dropbox_path()`, `ctx.dropbox_path`);
`molass_gui/app.py` (`_run`, `_connect_dropbox_dialog`); `molass_gui/notebook_export.py`
(`build_notebook`); `molass-library/molass/DataUtils/DropboxSync.py` (`on_status` param
on `sync_folder`).

---

## Original discussion (kept for history)

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

## Resolution (2026-09-13)

Point 1 (entry point) was superseded entirely — no separate button/dialog; see
"Final design" at the top. Points 2 and 3's leanings were adopted as-is (inline
connect-on-demand, paste-code flow). Point 4 was decided the *opposite* of the
original leaning: `dropbox` stays optional, not a hard dependency — missing-package
warns once and falls back to the plain local path. Point 5's `on_status` callback was
implemented as leaned. Point 6 (Recent Dropbox paths / `kind="dropbox"`) was dropped —
no longer needed since there's no separate Dropbox path entry to remember; the
existing single Recent list already covers it.

Remaining manual test (not yet run): fresh machine, no credentials, path containing
"dropbox" → connect flow → sync → Load → NaiveView; then a folder *without* "dropbox"
in the path to confirm zero behavior change.

---

## Known issue: possible user-count limitation on the Dropbox app (2026-09-15)

The Dropbox app registered for this integration is named `molass-data-sync`. Shimizu
tried to open its permissions page (presumably via the Dropbox App Console, to grant
himself access as a second user/tester) and got an error. The exact error message was
not captured, but it suggested some kind of limit on the number of users/testers
allowed on the app.

**Likely cause**: Dropbox apps in **"Development"** mode (the default for newly
created apps) are restricted to a small number of users (historically capped around
50, and the app owner must explicitly add each tester's Dropbox account email under
App Console → Permissions/Development users) before the app is submitted for
production approval. If `molass-data-sync` is still in Development mode, Shimizu's
account must be added to that allow-list first, or the cap may already be hit for
some other reason (e.g. team/business Dropbox restricting third-party app access
centrally).

**Action items** (not yet done):
- Re-attempt and capture the exact error text/screenshot when Shimizu next hits it.
- Check the app's status in the Dropbox App Console (Development vs. Production).
- If in Development mode, add Shimizu's Dropbox account explicitly as a permitted user.
- If a hard cap is actually the blocker, consider whether production approval is
  needed, or whether each collaborator should use their own personal Dropbox API app
  key/credentials instead of sharing one app (this integration's OAuth design already
  supports per-user `App Key` entry in the connect dialog, so this is a viable
  fallback without code changes).

### Coping options, ranked by effort

1. **Add Shimizu as a Development user on the existing app** (cheapest, try first).
   Dropbox App Console → `molass-data-sync` → Permissions tab → add Shimizu's
   Dropbox account email under the developer/tester allow-list. Only Takahashi (app
   owner) can do this. No code or workflow change; fixes it if the app is simply in
   Development mode with an unregistered-tester restriction.

2. **Reduce the requested scope to "App folder" access** instead of "Full Dropbox".
   Apps requesting broad/sensitive scopes are the ones Dropbox gates behind a
   dev-user allow-list or review; an app-folder-scoped app (data lives under
   `Apps/molass-data-sync/...` in each user's Dropbox) is usually exempt from that
   restriction entirely. Downside: requires the shared data to actually live inside
   that per-account app folder, which may mean restructuring how the shared dataset
   is placed/shared on Dropbox — a real (if one-time) change, not just settings.

3. **Each collaborator registers their own personal Dropbox app/App Key** and uses
   it with their own account. The connect dialog already asks for an `App Key`
   per-user (no code change needed) — Shimizu creates a trivial app under his own
   Dropbox developer account (a few minutes in the App Console), points it at the
   same shared Dropbox folder path, and authorizes with his own key. Sidesteps the
   whole "who's allowed to use *this* app" question since he'd own his app. This is
   the most robust fallback and matches how the OAuth flow was already designed.

4. **Share Takahashi's already-authorized credentials file directly** (fastest
   unblock, weakest security/hygiene). Copy `~/.molass/dropbox_credentials.json`
   (contains a refresh token tied to Takahashi's Dropbox identity) to Shimizu's
   machine. Works immediately with zero Dropbox Console interaction, but all syncs
   then act as Takahashi's account, and the token is a shared secret between two
   machines — acceptable only as a short-term stopgap between two trusted
   collaborators, not a real fix.

5. **Submit the app for Dropbox App Review** to move it to Production and remove
   any user cap entirely. Correct long-term fix if this integration is expected to
   grow beyond 2-3 collaborators, but disproportionate effort (privacy policy,
   review turnaround) for the current two-person use case.

**Recommendation**: try (1) first since it costs nothing; if the cap turns out to be
scope-related rather than a tester allow-list, fall back to (3) as the durable fix
without touching `molass-library`/`molass-gui` code at all.

**Resolved (2026-09-15)**: it was option (1) — the App Console had a "Development
users" cap. Takahashi raised the limit to 500, which should be more than enough
headroom for the foreseeable collaborator count. Pending confirmation: Shimizu
retries the connect flow and successfully authorizes.

---

## Feature-flagged behind `--dropbox-support` (2026-09-15)

Until the fix above has been confirmed end-to-end with a second real user, the
whole feature is suppressed by default rather than silently active for anyone
whose folder path happens to contain "dropbox":

- New module `molass_gui/feature_flags.py`: module-level
  `DROPBOX_SUPPORT_ENABLED = False`.
- `launcher.py` `main()` parses `--dropbox-support` (argparse `store_true`) and
  sets the flag before `Launcher().mainloop()`.
- `app.py`'s `_run()`: both the credential-check branch and the worker-thread
  sync branch are now gated with
  `feature_flags.DROPBOX_SUPPORT_ENABLED and "dropbox" in folder.lower()`.
  When disabled, a Dropbox-looking folder path is loaded exactly like any
  other local path -- no credential prompt, no sync, no status text.
- `session_context.py`'s `SessionContext.dropbox_path` property returns `None`
  unconditionally when the flag is off, so `notebook_export.py`'s
  `build_notebook()` never emits a `sync_dropbox_folder(...)` cell either --
  load-time and export-time behavior stay consistent.
- Run with the feature on: `python -m molass_gui.launcher --dropbox-support`
  (or however the installed console-script entry point is invoked, with the
  same flag appended).

Once Shimizu's authorization is confirmed working and a bit more real-world
use has happened, the flag's default can flip to `True` (or be removed
entirely so the feature is simply always-on again).

