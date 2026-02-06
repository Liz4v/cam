from pathlib import Path
from types import SimpleNamespace

import wwpppp.main as mainmod
from wwpppp.geometry import Point, Rectangle, Size, Tile


def test_main_forget_removes_tile_key(monkeypatch):
    # start with no projects
    class FakeProjectClass:
        @classmethod
        def iter(cls):
            return []

        @classmethod
        def try_open(cls, p):
            return None

    monkeypatch.setattr(mainmod, "Project", FakeProjectClass)
    m = mainmod.Main()

    # create a fake project and tile mapping
    path = Path("/tmp/p.png")

    class FakeProj:
        def __init__(self, path, rect):
            self.path = path
            self.rect = rect

        def forget(self):
            return None

        def __hash__(self):
            return hash(self.path)

        def __eq__(self, other):
            return getattr(other, "path", None) == self.path

    proj = FakeProj(path, Rectangle.from_point_size(Point(0, 0), Size(1000, 1000)))
    tile = Tile(0, 0)
    m.projects[path] = proj
    m.tiles[tile] = {proj}

    m.forget_project(path)
    assert tile not in m.tiles


def test_load_project_none(monkeypatch):
    # start with no projects
    class FakeProjectClass:
        @classmethod
        def iter(cls):
            return []

        @classmethod
        def try_open(cls, p):
            return None

    monkeypatch.setattr(mainmod, "Project", FakeProjectClass)
    m = mainmod.Main()
    path = Path("/tmp/nothing.png")
    # should not raise and not add the project
    m.load_project(path)
    assert path not in m.projects
