from pathlib import Path
from types import SimpleNamespace

from wwpppp import projects
from wwpppp.geometry import Point, Rectangle, Size
from wwpppp.palette import PALETTE


def test_try_open_cached_bad_cache(monkeypatch, tmp_path):
    # create a valid paletted image file
    path = tmp_path / "proj_2_2_0_0.png"
    im = PALETTE.new((2, 2))
    im.putdata([1, 1, 1, 1])
    im.save(path)

    # fake cache that is truthy but yields wrong data (causes TypeError on cls(path, *cached))
    class FakeCache(list):
        def __init__(self, p):
            super().__init__([1, 2, 3])

        def __bool__(self):
            return True

        def __call__(self, rect=None):
            if rect is None:
                return []
            return [rect]

    monkeypatch.setattr(projects, "CachedProjectMetadata", FakeCache)
    # should not raise; try_open will catch TypeError and proceed
    res = projects.Project.try_open(path)
    assert res is not None


def test_try_open_cached_good_cache(monkeypatch, tmp_path):
    # create a valid paletted image file
    path = tmp_path / "proj_3_3_0_0.png"
    im = PALETTE.new((2, 2))
    im.putdata([1, 1, 1, 1])
    im.save(path)

    rect = Rectangle.from_point_size(Point.from4(3, 3, 0, 0), Size(2, 2))

    class FakeCache(list):
        def __init__(self, p):
            super().__init__([rect])

        def __bool__(self):
            return True

    monkeypatch.setattr(projects, "CachedProjectMetadata", FakeCache)
    res = projects.Project.try_open(path)
    assert res is not None
    assert res.rect == rect
