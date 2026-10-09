# Installing Molass GUI (Windows)

This page is for **beginners with no Python experience**. If you already have
Python installed and are comfortable with `pip`, see the
[Developer install](#developer-install-pip) section at the bottom instead —
it's simpler for that audience.

## Download

1. Go to the [Releases page](https://github.com/biosaxs-dev/molass-gui/releases).
2. Under the latest release, download the file named
   `molass-gui-<version>-portable-win64.zip`.
3. **Right-click the downloaded zip → Extract All…** and choose a folder you
   can find easily (e.g. your Desktop or Documents). Do **not** try to run
   the program directly from inside the zip file — it must be extracted
   first.

   > **This step can take a few minutes.** The zip contains several thousand
   > small files (the Python runtime and all of Molass's dependencies), and
   > Windows' built-in "Extract All" — like most antivirus-scanned
   > extractors — is noticeably slower on many-small-files archives than on
   > a single large file. This is normal; it is not stuck.

No installer runs, nothing is written outside the folder you extracted to,
and no administrator rights are needed — the whole program, including its
own copy of Python, lives inside that one folder.

## Run it

Open the extracted folder and double-click **`molass-gui.bat`**.

A window titled **Molass** should appear after a few seconds. If a security
warning appears first, see [Windows SmartScreen warning](#windows-smartscreen-warning)
below.

## Try it with sample data

The GUI needs a folder of SEC-SAXS data to analyze. If you don't have your
own data yet, Molass ships with public sample datasets for exactly this
purpose — see the [Quick Start guide](quickstart.md), which walks through a
complete analysis using one of them (`SAMPLE1`), with screenshots of every
step.

## Troubleshooting

### Windows SmartScreen warning

Because this build isn't digitally signed by a registered publisher, Windows
may show a blue "Windows protected your PC" screen the first time you run
`molass-gui.bat`. Click **More info**, then **Run anyway**. This is expected
for small open-source projects distributed outside the Microsoft Store and
does not indicate a problem with the download.

### Antivirus flags the extraction or the folder

Some antivirus products scan every file during a large extraction, which can
make it feel stuck — give it a few minutes before assuming something is
wrong. If your antivirus quarantines a specific file afterward, it is almost
always a false positive on one of the bundled scientific-Python native
libraries (e.g. `numba`/`llvmlite`); restoring it from quarantine is safe.

### The window never appears / closes immediately

Make sure you extracted the whole zip (not just opened it) and are running
`molass-gui.bat` from inside the extracted folder, not from inside the zip
itself (Windows lets you browse into a zip without extracting it, but
programs can't run correctly from there).

If it still doesn't work, please
[open an issue](https://github.com/biosaxs-dev/molass-gui/issues/new) —
include what you see (or a screenshot) and your Windows version.

## Developer install (pip)

If you already have Python 3.9–3.14 installed:

```
pip install molass-gui
molass-gui
```

See the [repository README](https://github.com/biosaxs-dev/molass-gui#readme)
for details and version requirements. This route also works on macOS/Linux,
unlike the portable zip above, which is Windows-only.
