# molass_gui changelog

Newest first. This file ships inside the installed package, next to `CONTEXT.md`
(`os.path.join(os.path.dirname(molass_gui.__file__), "CHANGELOG.md")`). The GUI is a Tkinter wizard over the `molass`
pipeline; what a menu or button does is a `molass` call, listed in `CONTEXT.md`. Issue numbers are of
`biosaxs-dev/molass-gui` unless written out. Versions before 0.7.0: see the GitHub Releases.

Headings: **Changed (behavior)**, **Added**, **Requires**.

## 0.7.0 (2026-11-18)

Headline: **Continue as new analysis...** starts a new analysis from the best result under the same or another elution model,
and the result windows are independent of each other.

### Changed (behavior)
- **Closing a result window, a forked window or the window it was forked from closes that window only**, not the whole session
  (it asks first if its own optimization is running). The other phase windows (Naive, Quick, Upgraded) and the launcher still
  end the whole session.
- **Open Existing Analysis** keeps its dialog on screen, with the current stage ("Loading the data", "Trimming", ...), until the
  result window is drawn; the new window opens only then, and a failed load comes back to the dialog with the message. Before,
  the dialog disappeared and a blank window waited for minutes.
- The Rg curve is computed in a child process (biosaxs-dev/molass-library#400), so Tk drawing is no longer slowed down while
  it runs (#23). With a `molass` before 1.3.0 it falls back to a thread.
- The folder box and the Recent list of the folder pickers are as wide as the longest recent path.

### Added
- **Continue as new analysis...** in the result view (for a loaded result or a stopped run): a dialog for the new folder, the model
  (GRM or LKM may start near the current curves), the method and the number of jobs; **Prepare** shows the score of the start,
  **Start** opens a live window for the new folder, seeded from the best result (`molass.fork_analysis`, biosaxs-dev/molass-library#396).
  The button is hidden when the installed `molass` has no `fork_analysis`.
- Naive View: **Show trimming...** (the trimming the session used, on the entire data) and **Show mapping...** (the UV/XR mapping
  of the trimming: overlay, matched peak pairs with the fitted line, plausibility numbers).

### Requires
`molass>=1.3.0`, `molass_legacy>=1.7.3`, Python 3.9 to 3.14 as before. Windows portable zip: `molass-gui-0.7.0-portable-win64.zip` on the
GitHub Release.
