import queue
import threading
import time
from types import SimpleNamespace

import numpy as np

from molass_gui import rgcurve_worker
from molass_gui.rgcurve_worker import start_rgcurve_computation, stop_rgcurve_computation


class FakeJob:
    def __init__(self, outcomes, n_done=(0,)):
        self._outcomes = list(outcomes)
        self._n_done = list(n_done)
        self.cancelled = False
        self.closed = False

    def poll(self):
        return self._outcomes.pop(0) if len(self._outcomes) > 1 else self._outcomes[0]

    def progress(self):
        n = self._n_done.pop(0) if len(self._n_done) > 1 else self._n_done[0]
        return n, None

    def cancel(self):
        self.cancelled = True

    def close(self):
        self.closed = True


class FakeSsd:
    def __init__(self, job):
        self._job = job

    def start_rg_curve_process(self):
        return self._job


def drain(q, until, timeout=10):
    messages = []
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        try:
            messages.append(q.get(timeout=0.1))
        except queue.Empty:
            continue
        if messages[-1][0] in until:
            break
    return messages


def test_the_process_job_is_turned_into_the_queue_messages(monkeypatch):
    monkeypatch.setattr(rgcurve_worker, "PUMP_INTERVAL", 0.01)
    job = FakeJob([None, None, ("done", "curve")], n_done=[0, 3, 5])
    messages = drain(start_rgcurve_computation(FakeSsd(job)), until={"done"})
    assert messages == [("progress", 2), ("progress", 4), ("done", "curve")]


def test_a_failed_process_is_reported_as_one_line(monkeypatch):
    monkeypatch.setattr(rgcurve_worker, "PUMP_INTERVAL", 0.01)
    job = FakeJob([("error", "ValueError: bad\nTraceback ...")])
    assert drain(start_rgcurve_computation(FakeSsd(job)), until={"error"}) == [("error", "ValueError: bad")]


def test_stopping_cancels_the_job(monkeypatch):
    monkeypatch.setattr(rgcurve_worker, "PUMP_INTERVAL", 0.01)
    job = FakeJob([None])
    q = start_rgcurve_computation(FakeSsd(job))
    stop_rgcurve_computation(q)
    t0 = time.monotonic()
    while not job.cancelled and time.monotonic() - t0 < 10:
        time.sleep(0.02)
    assert job.cancelled


def test_a_decomposition_gets_the_curve_it_caches_itself(monkeypatch):
    monkeypatch.setattr(rgcurve_worker, "PUMP_INTERVAL", 0.01)
    ssd = FakeSsd(FakeJob([("done", "slim")]))
    decomp = SimpleNamespace(ssd=ssd, get_rg_curve=lambda: "cached")
    assert drain(start_rgcurve_computation(decomp), until={"done"}) == [("done", "cached")]


def test_without_a_process_job_the_plain_thread_is_used():
    obj = SimpleNamespace(get_rg_curve=lambda progress_cb=None: progress_cb(None, 0) or "curve")
    assert drain(start_rgcurve_computation(obj), until={"done"}) == [("progress", 0), ("done", "curve")]


def test_a_curve_that_is_already_known_does_not_start_a_process():
    started = []
    ssd = SimpleNamespace(start_rg_curve_process=lambda: started.append(1))
    decomp = SimpleNamespace(ssd=ssd, has_rg_curve=True, get_rg_curve=lambda progress_cb=None: "known")
    assert drain(start_rgcurve_computation(decomp), until={"done"}) == [("done", "known")]
    assert started == []


def test_a_real_child_process_delivers_the_curve():
    from molass.Testing import Species, simulate_ssd
    ssd = simulate_ssd([Species(amp=1.0, center=30, sigma=5, mass=2.0, rg=36.0)], noise=1.0, seed=1,
                       xr_frames=np.arange(60))
    messages = drain(start_rgcurve_computation(ssd), until={"done", "error"}, timeout=300)
    assert messages[-1][0] == "done" and len(messages[-1][1].frames) == 60
    assert ssd.get_rg_curve() is messages[-1][1]
