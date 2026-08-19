"""Lightweight "recently used folders" persistence for Phase 1's data-folder picker.

Stores a small JSON file under the user's home directory. Deliberately not based
on molass-legacy's KekLib/RecentFolders.py, which requires the legacy `Settings`
global-state singleton to persist its own recent_folders/num_recent_folders
values -- unwanted baggage for a standalone GUI.
"""
import json
from pathlib import Path

_MAX_ENTRIES = 10
_STATE_PATH = Path.home() / ".molass-gui" / "recent_folders.json"


def load():
    """Return recent folder paths, most-recently-used first."""
    try:
        return json.loads(_STATE_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def add(path):
    """Record *path* as just used, moving it to the front if already present.

    Returns the updated list.
    """
    folders = [p for p in load() if p != path]
    folders.insert(0, path)
    folders = folders[:_MAX_ENTRIES]
    _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STATE_PATH.write_text(json.dumps(folders, indent=2), encoding="utf-8")
    return folders
