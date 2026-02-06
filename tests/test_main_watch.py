from pathlib import Path
from types import SimpleNamespace

from watchfiles import Change

import wwpppp.main as mainmod


def test_watch_for_updates_added_and_deleted(monkeypatch):
    # create a fake project and Main instance
    proj_path = Path("/tmp/p.png")
    proj = SimpleNamespace(path=proj_path, rect=SimpleNamespace(tiles={}), run_diff=lambda: None, forget=lambda: None)

    # monkeypatch Project as a class with classmethods
    class FakeProjectClass:
        @classmethod
        def iter(cls):
            return [proj]

        @classmethod
        def try_open(cls, p):
            return proj

    monkeypatch.setattr(mainmod, "Project", FakeProjectClass)

    m = mainmod.Main()

    # monkeypatch TilePoller as context manager that yields
    class DummyPoller:
        def __init__(self, cb, tiles):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(mainmod, "TilePoller", DummyPoller)

    # patch watch_loop to yield one added and one deleted event
    monkeypatch.setattr(
        mainmod.Main, "watch_loop", lambda self: iter([(Change.added, proj_path), (Change.deleted, proj_path)])
    )

    # run watch_for_updates (should not raise)
    m.watch_for_updates()
