"""Lightweight "recently used folders" persistence, shared by the New Analysis
data-folder picker and the Open Existing Analysis analysis-folder picker.

Stores a small JSON file per *kind* under the user's home directory. Deliberately
not based on molass-legacy's KekLib/RecentFolders.py, which requires the legacy
`Settings` global-state singleton to persist its own recent_folders/
num_recent_folders values -- unwanted baggage for a standalone GUI.
"""
import json
from pathlib import Path

_MAX_ENTRIES = 10
_STATE_DIR = Path.home() / ".molass-gui"

# the folder box and the Recent list are as wide as the longest recent path (a list is no wider than its box:
# paths cut off at the end cannot be told apart), within these limits (in characters)
MIN_WIDTH = 52
MAX_WIDTH = 100


def picker_width(paths, minimum=MIN_WIDTH, maximum=MAX_WIDTH):
    """Width in characters for the folder entry and the Recent combobox: the longest path plus a margin (the
    default font is proportional, so a path of n characters can need more than n), kept within the limits."""
    longest = max((len(p) for p in paths), default=0)
    return max(minimum, min(maximum, longest + 6))


def _state_path(kind):
    suffix = "" if kind == "data" else f"_{kind}"
    return _STATE_DIR / f"recent_folders{suffix}.json"


def load(kind="data"):
    """Return recent folder paths for *kind* ('data' or 'analysis'), most-recently-used first."""
    try:
        return json.loads(_state_path(kind).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def add(path, kind="data"):
    """Record *path* as just used for *kind*, moving it to the front if already present.

    Returns the updated list.
    """
    folders = [p for p in load(kind) if p != path]
    folders.insert(0, path)
    folders = folders[:_MAX_ENTRIES]
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    _state_path(kind).write_text(json.dumps(folders, indent=2), encoding="utf-8")
    return folders

