# molass_gui changelog

Newest first. This file ships inside the installed package, next to `CONTEXT.md`
(`os.path.join(os.path.dirname(molass_gui.__file__), "CHANGELOG.md")`). The GUI is a Tkinter wizard over the `molass`
pipeline; what a menu or button does is a `molass` call, listed in `CONTEXT.md`. Issue numbers are of
`biosaxs-dev/molass-gui` unless written out. Versions before 0.7.0: see the GitHub Releases.

Headings: **Changed (behavior)**, **Added**, **Requires**.

## Unreleased

### Changed (behavior)
- **Applying Ranks = 2 in the Quick View leads with the impact** (#26): a row of its own under the header (not the header's status line, where it widened the
  window) says how much the correction changes the Rg
  (`Ranks = 2: Rg 35.2 -> 34.2 A (-2.8 %, adaptive fit); 30.3 -> 33.4 A (+10.4 %, from the lowest q) | 2 checks flagged (see the notice)`), from
  `decomposition.rank2_report()`. With a `molass` that has the findings (biosaxs-dev/molass-library#423) the notice bar lists each check in plain
  language, what it affects and what to check, with the library's own text under it; it says that a finding is not a risk level (the thresholds are
  provisional). With an older `molass` the generic notice of #25 stays, and a missing or failing report never breaks applying the ranks.
- **Applying Ranks in the Quick View shows what molass says** (#25): the warnings of the rank-2 (interparticle) correction (the concentration
  refinement ended at a bound, B/A exceeds the hard-core envelope, K is small, ...) go to the notice bar below the header, with a
  plain-language first line and the library's texts under Details; they go away when the ranks are applied without a rank-2 component.
  A rank-2 component without the stated error (a `ValueError` of `molass` naming the cause, biosaxs-dev/molass-library#421) leaves
  the earlier ranks in place and says why in the status line, instead of an unhandled error.

### Added
- **The exported notebook shows what the rank-2 correction did** (#28): when the Ranks contain 2, a cell right after the one that applies them prints
  `decomp.rank2_report()` (guarded for a `molass` without it), with a note on `set_rank2_method('bounded')`. Without a rank-2 component the export is unchanged.
- **Rank-2 report...** button in the Quick View (#27), in the row of the rank-2 summary (it exists only with a rank-2 component, and the header keeps its
  width): opens `decomposition.rank2_report()` as read-only monospace text with **Copy to Clipboard**, to paste into a status record or a mail. It is the
  report computed when the ranks were applied; nothing can be edited (it shows what the data support, it is not a tuning panel).

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
