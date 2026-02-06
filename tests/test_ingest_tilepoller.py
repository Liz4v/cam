from types import SimpleNamespace

import wwpppp.ingest as ingest


def test_tilepoller_context_manager(monkeypatch):
    events = []

    class FakeThread:
        def __init__(self, *a, **k):
            pass

        def start(self):
            events.append("start")

        def join(self, timeout=None):
            events.append("join")

    monkeypatch.setattr(ingest, "Thread", FakeThread)
    tp = ingest.TilePoller(lambda t: None, [])
    with tp:
        pass
    assert events == ["start", "join"]


def test_tilepoller_run_checks_stop():
    tp = ingest.TilePoller(lambda t: None, [ingest.Tile(0, 0)])
    # replace internal _stop with object where is_set False but wait returns True to exit early
    tp._stop = type("S", (), {"is_set": staticmethod(lambda: False), "wait": staticmethod(lambda t: True)})()
    # should return quickly without raising
    tp._run()
