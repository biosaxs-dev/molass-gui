"""The launcher's --no-anomaly-handling flag switches molass's anomaly handling off for the whole GUI process."""
import sys

import pytest

from molass.Global.Options import get_molass_options, set_molass_options

from molass_gui import launcher


class _FakeLauncher:
    started = False

    def mainloop(self):
        _FakeLauncher.started = True


@pytest.fixture
def run_main(monkeypatch):
    before = get_molass_options('anomaly_handling')
    monkeypatch.setattr(launcher, "Launcher", _FakeLauncher)
    monkeypatch.setattr(launcher, "_enable_crash_log", lambda: None)

    def run(*argv):
        _FakeLauncher.started = False
        monkeypatch.setattr(sys, "argv", ["molass-gui", *argv])
        launcher.main()
        assert _FakeLauncher.started

    yield run
    set_molass_options(anomaly_handling=before)


def test_default_keeps_anomaly_handling_on(run_main):
    set_molass_options(anomaly_handling=True)
    run_main()
    assert get_molass_options('anomaly_handling') is True


def test_flag_switches_it_off(run_main):
    set_molass_options(anomaly_handling=True)
    run_main("--no-anomaly-handling")
    assert get_molass_options('anomaly_handling') is False


def test_flag_is_listed_in_help(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["molass-gui", "--help"])
    with pytest.raises(SystemExit):
        launcher.main()
    assert "--no-anomaly-handling" in capsys.readouterr().out
