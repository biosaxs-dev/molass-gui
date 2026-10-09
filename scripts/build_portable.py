"""Build a self-contained, portable Windows distribution of molass-gui.

Bundles the official python.org *embeddable* Python distribution (no
installer, no admin rights, no existing Python required on the target
machine), adds Tcl/Tk support (deliberately excluded from the embeddable
package), pip-installs molass-gui into it, and zips the result together
with a double-click launcher.

Usage (must be run with the same Python major.minor version as PYTHON_VERSION
below -- that interpreter's own install is used as the source for the Tcl/Tk
files, which the embeddable package does not ship):

    py -3.14 scripts\\build_portable.py

Output: dist\\molass-gui-<version>-portable-win64.zip

See molass-legacy/molass_legacy/Build/Embeddables.py for the prior art this
was adapted from (same Tcl/Tk bundling facts -- notably that zlib1.dll is
also required, undocumented, from Python 3.12 onward -- but without its
dynamic "scrape python.org for the latest version" and Gohlke-fallback
machinery, neither of which is needed now that every molass-gui dependency
ships an official Windows wheel).
"""
import argparse
import os
import platform
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

# Pinned rather than auto-detected: reproducible builds, no scraping of
# python.org needed. Bump manually when a newer Python is wanted.
PYTHON_VERSION = "3.14.4"
PYTHON_TAG = "python" + "".join(PYTHON_VERSION.split(".")[:2])  # "python314"

REPO_ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = REPO_ROOT / "build" / "portable"
DIST_DIR = REPO_ROOT / "dist"
EMBED_DIR = BUILD_DIR / "python"
# Deliberately outside BUILD_DIR: BUILD_DIR's contents are exactly what gets
# zipped into the distributable, and the download cache (the raw embeddable
# zip, get-pip.py) must not end up inside it.
CACHE_DIR = REPO_ROOT / "build" / "cache"

# Tcl/Tk is deliberately excluded from the embeddable package. These are the
# files that must be copied in from a regular, same-version Python install.
# zlib1.dll is the easy-to-miss one: undocumented, but _tkinter.pyd fails to
# load without it from Python 3.12 onward.
TKINTER_DLLS = ["_tkinter.pyd", "tcl86t.dll", "tk86t.dll", "zlib1.dll"]
TKINTER_FOLDERS = ["tcl", "Lib/tkinter"]


def log(msg):
    print(f"[build_portable] {msg}")


def download(url, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        log(f"using cached {dest.name}")
        return dest
    log(f"downloading {url}")
    urllib.request.urlretrieve(url, dest)
    return dest


def check_build_interpreter():
    """The build must run under the same major.minor Python it's packaging,
    since that interpreter's own install is the source of the Tcl/Tk files."""
    running = platform.python_version_tuple()[:2]
    wanted = PYTHON_VERSION.split(".")[:2]
    if list(running) != wanted:
        sys.exit(
            f"This script must be run with Python {'.'.join(wanted)}.x "
            f"(currently running {platform.python_version()}). "
            f"Try: py -{wanted[0]}.{wanted[1]} scripts\\build_portable.py"
        )


def prepare_embeddable():
    if EMBED_DIR.exists():
        shutil.rmtree(EMBED_DIR)
    zip_path = download(
        f"https://www.python.org/ftp/python/{PYTHON_VERSION}/"
        f"python-{PYTHON_VERSION}-embed-amd64.zip",
        CACHE_DIR / f"python-{PYTHON_VERSION}-embed-amd64.zip",
    )
    log(f"extracting embeddable package to {EMBED_DIR}")
    with zipfile.ZipFile(zip_path) as zh:
        zh.extractall(EMBED_DIR)


def patch_pth_file():
    """Enable site-packages processing (needed for pip-installed packages)
    and add a .\\DLLs subfolder to the search path, matching the layout of a
    regular Python install (same convention used by Embeddables.py, chosen
    so it keeps working across future Python version bumps the same way)."""
    pth_file = EMBED_DIR / f"{PYTHON_TAG}._pth"
    text = pth_file.read_text(encoding="utf-8")
    text = text.replace("#import site", "import site")
    lines = text.splitlines()
    insert_at = 2  # after "pythonXXX.zip" and "."
    for extra in (".\\Scripts", ".\\Lib", ".\\DLLs"):
        lines.insert(insert_at, extra)
    pth_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log(f"patched {pth_file.name}")


def bootstrap_pip():
    get_pip = download(
        "https://bootstrap.pypa.io/get-pip.py", CACHE_DIR / "get-pip.py"
    )
    python_exe = EMBED_DIR / "python.exe"
    run([str(python_exe), str(get_pip), "--no-warn-script-location"])


def run(cmd, **kwargs):
    log("+ " + " ".join(cmd))
    env = dict(os.environ, PYTHONNOUSERSITE="1")
    subprocess.run(cmd, check=True, env=env, **kwargs)


WHEEL_DIR = REPO_ROOT / "build" / "wheel"


def resolve_install_target(source):
    """If 'source' is a local checkout (the default), build its wheel with
    the *host* Python first and install that wheel file instead.

    This matters because installing a local source directory straight into
    the embeddable env would require pip to invoke molass-gui's build
    backend (hatchling) *inside* that env -- which --only-binary=:all: then
    blocks from being fetched, failing with
    "BackendUnavailable: Cannot import 'hatchling.build'". Building the
    wheel with the host's own unrestricted pip sidesteps that entirely: the
    embeddable env only ever installs already-built wheels, local or not."""
    if not Path(source).is_dir():
        return source  # e.g. "molass-gui==0.4.2" -- installed from PyPI as-is

    if WHEEL_DIR.exists():
        shutil.rmtree(WHEEL_DIR)
    WHEEL_DIR.mkdir(parents=True)
    run([sys.executable, "-m", "pip", "wheel", "--no-deps", "-w", str(WHEEL_DIR), source])
    wheels = list(WHEEL_DIR.glob("*.whl"))
    assert len(wheels) == 1, f"expected exactly one wheel, got {wheels}"
    return str(wheels[0])


def install_molass_gui(source):
    target = resolve_install_target(source)
    python_exe = EMBED_DIR / "python.exe"
    run([
        str(python_exe), "-m", "pip", "install",
        "--no-warn-script-location", "--no-cache-dir",
        "--only-binary=:all:",
        target,
    ])


# Bundling full molass_data (~120 MB, 5 datasets) would roughly double the
# zip's size; SAMPLE1 alone is a 13 MB download that's enough for the Quick
# Start guide's walkthrough. Trimmed post-install rather than hand-copied,
# so pip still records it as a real, upgradable, version-tracked dependency.
BUNDLED_SAMPLES = ["SAMPLE1"]
ALL_SAMPLE_NAMES = ["SAMPLE1", "SAMPLE2", "SAMPLE3", "SAMPLE4", "SAMPLE5"]


def bundle_sample_data():
    python_exe = EMBED_DIR / "python.exe"
    run([
        str(python_exe), "-m", "pip", "install",
        "--no-warn-script-location", "--no-cache-dir",
        "--only-binary=:all:",
        "molass_data",
    ])

    pkg_dir = EMBED_DIR / "Lib" / "site-packages" / "molass_data"
    for name in ALL_SAMPLE_NAMES:
        if name not in BUNDLED_SAMPLES:
            shutil.rmtree(pkg_dir / name)

    # Trim __init__.py's SAMPLE*=get_data_path(...) assignments to match --
    # naive_view.py's sample dropdown lists every SAMPLE* attribute it
    # defines, regardless of whether the folder actually exists, so a
    # stale assignment would offer a selection that fails when loaded.
    init_path = pkg_dir / "__init__.py"
    lines = init_path.read_text(encoding="utf-8").splitlines(keepends=True)
    lines = [
        l for l in lines
        if not (l.startswith("SAMPLE") and l.split("=")[0].strip() not in BUNDLED_SAMPLES)
    ]
    init_path.write_text("".join(lines), encoding="utf-8")
    log(f"bundled sample data: {', '.join(BUNDLED_SAMPLES)}")


def bundle_tkinter():
    local_python_dir = Path(sys.executable).resolve().parent
    dlls_dir = EMBED_DIR / "DLLs"
    dlls_dir.mkdir(exist_ok=True)

    for name in TKINTER_DLLS:
        src = local_python_dir / "DLLs" / name
        if not src.exists():
            # Diagnostic dump rather than a bare error: actions/setup-python's
            # hosted Windows Python has been observed to lay out (or omit)
            # Tcl/Tk differently from a standard python.org installer -- show
            # what's actually there so this is fixable from CI logs alone.
            log(f"ERROR: missing {src}")
            log(f"contents of {local_python_dir}:")
            for p in sorted(local_python_dir.glob("*")):
                log(f"  {p.name}")
            log(f"contents of {local_python_dir / 'DLLs'} (if present):")
            dlls_src_dir = local_python_dir / "DLLs"
            if dlls_src_dir.exists():
                for p in sorted(dlls_src_dir.glob("*tcl*")) + sorted(dlls_src_dir.glob("*tk*")):
                    log(f"  {p.name}")
            else:
                log("  (no DLLs folder at all)")
            log(f"contents of {local_python_dir / 'Lib'} (tkinter-related):")
            lib_dir = local_python_dir / "Lib"
            if lib_dir.exists():
                for p in sorted(lib_dir.glob("*tk*")):
                    log(f"  {p.name}")
            sys.exit(1)
        shutil.copy2(src, dlls_dir / name)

    for rel in TKINTER_FOLDERS:
        src = local_python_dir / rel
        dst = EMBED_DIR / rel
        if dst.exists():
            continue
        shutil.copytree(src, dst)

    log("bundled Tcl/Tk (" + ", ".join(TKINTER_DLLS) + ")")


def write_launcher():
    launcher = BUILD_DIR / "molass-gui.bat"
    launcher.write_text(
        "@echo off\r\n"
        "set PYTHONNOUSERSITE=1\r\n"
        "set TCL_LIBRARY=%~dp0python\\tcl\\tcl8.6\r\n"
        "set TK_LIBRARY=%~dp0python\\tcl\\tk8.6\r\n"
        'start "" "%~dp0python\\pythonw.exe" -m molass_gui.launcher %*\r\n',
        encoding="utf-8",
    )
    log(f"wrote {launcher.name}")


def read_version():
    import tomllib
    # tomllib.loads wants str; read as bytes+decode explicitly rather than
    # Path.read_text() so this doesn't depend on the OS's default codepage
    # (pyproject.toml's description field has a non-ASCII em dash, which
    # read_text()'s cp932 default on ja-JP Windows fails to decode).
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_bytes().decode("utf-8"))
    return data["project"]["version"]


def make_zip():
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    version = read_version()
    zip_path = DIST_DIR / f"molass-gui-{version}-portable-win64.zip"
    if zip_path.exists():
        zip_path.unlink()
    log(f"zipping to {zip_path}")
    base_name = str(zip_path.with_suffix(""))
    shutil.make_archive(base_name, "zip", root_dir=BUILD_DIR)
    return zip_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", default=str(REPO_ROOT),
        help="what to 'pip install' (default: this repo checkout; "
             "use e.g. molass-gui==0.4.2 to install a published release)",
    )
    args = parser.parse_args()

    check_build_interpreter()
    prepare_embeddable()
    patch_pth_file()
    bootstrap_pip()
    install_molass_gui(args.source)
    bundle_sample_data()
    bundle_tkinter()
    write_launcher()
    zip_path = make_zip()
    log(f"done: {zip_path}")


if __name__ == "__main__":
    main()
