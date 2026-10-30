"""Under pythonw.exe (the portable molass-gui.bat) sys.stdout/sys.stderr are None, which made every tqdm bar in molass fail
with "'NoneType' object has no attribute 'write'" (seen as "Rg error: ..." in Quick View)."""
import sys

from molass_gui import launcher


def _no_console(monkeypatch, tmp_path):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)


def test_missing_streams_are_redirected_to_a_log_file(monkeypatch, tmp_path):
    _no_console(monkeypatch, tmp_path)
    launcher._ensure_std_streams()
    try:
        assert sys.stdout is not None and sys.stderr is not None
        print("hello", file=sys.stdout)
        print("oops", file=sys.stderr)
    finally:
        sys.stdout.close()
    log = (tmp_path / ".molass" / "gui.log").read_text(encoding="utf-8")
    assert "hello" in log and "oops" in log


def test_tqdm_works_without_a_console(monkeypatch, tmp_path):
    from tqdm import tqdm
    _no_console(monkeypatch, tmp_path)
    launcher._ensure_std_streams()
    try:
        assert list(tqdm(range(3))) == [0, 1, 2]
    finally:
        sys.stdout.close()


def test_existing_streams_are_left_alone(monkeypatch, tmp_path):
    out, err = sys.stdout, sys.stderr
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    launcher._ensure_std_streams()
    assert sys.stdout is out and sys.stderr is err
    assert not (tmp_path / ".molass").exists()
