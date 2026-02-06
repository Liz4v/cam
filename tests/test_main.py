from pathlib import Path
from types import SimpleNamespace

from wwpppp.geometry import Point, Rectangle, Size, Tile
from wwpppp.main import Main


def test_main_load_and_consume(monkeypatch):
    # create a fake project with a rect covering tile (0,0)
    proj_path = Path("/tmp/proj.png")

    class FakeProj:
        def __init__(self, path, rect):
            self.path = path
            self.rect = rect
            self._called = {"run_diff": 0, "forget": 0}

        def run_diff(self):
            self._called["run_diff"] += 1

        def forget(self):
            self._called["forget"] += 1

        def __hash__(self):
            return hash(self.path)

        def __eq__(self, other):
            return getattr(other, "path", None) == self.path

    proj = FakeProj(proj_path, Rectangle.from_point_size(Point(0, 0), Size(1000, 1000)))

    # monkeypatch Project.iter and Project.try_open
    monkeypatch.setattr("wwpppp.main.Project.iter", classmethod(lambda cls: [proj]))
    monkeypatch.setattr("wwpppp.main.Project.try_open", classmethod(lambda cls, p: proj))

    m = Main()
    # consume tile should call project's run_diff
    m.consume_new_tile(Tile(0, 0))
    assert proj._called["run_diff"] == 1

    # forget project removes tiles and calls forget()
    m.forget_project(proj_path)
    assert proj._called["forget"] == 1

    # loading project back adds it again
    m.load_project(proj_path)
    assert proj_path in m.projects
