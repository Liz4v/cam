from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from wwpppp import projects
from wwpppp.geometry import Point, Rectangle, Size
from wwpppp.palette import PALETTE, ColorNotInPalette


def test_try_open_no_coords(tmp_path):
    p = tmp_path / "no_coords.png"
    p.write_bytes(b"x")
    assert projects.Project.try_open(p) is None


def test_try_open_invalid_color(tmp_path, monkeypatch):
    # write an image with a color not in the palette
    path = tmp_path / "proj_0_0_0_0.png"
    im = Image.new("RGBA", (2, 2), (250, 251, 252, 255))
    im.save(path)

    # ensure caching is a no-op to avoid sqlite
    monkeypatch.setattr(projects, "CachedProjectMetadata", lambda p: SimpleNamespace(__bool__=lambda: False))

    # try_open should detect color not in palette and rename the file
    res = projects.Project.try_open(path)
    assert res is None
    assert path.with_suffix(".invalid.png").exists()


def test_try_open_valid_project_and_run_diff(tmp_path, monkeypatch):
    # create a correct paletted image
    path = tmp_path / "proj_1_1_0_0.png"
    im = PALETTE.new((10, 10))
    im.putdata([1] * 100)
    im.save(path)

    # fake CachedProjectMetadata so it stores and returns rect
    class FakeCache(list):
        def __init__(self, path):
            super().__init__([])

        def __call__(self, rect=None):
            if rect is None:
                return []
            self.clear()
            self.append(rect)
            return self

    monkeypatch.setattr(projects, "CachedProjectMetadata", FakeCache)

    # monkeypatch stitch_tiles to return identical image -> run_diff should be quick
    monkeypatch.setattr(projects, "stitch_tiles", lambda rect: PALETTE.new((10, 10)))
    # avoid heavy logging or side effects
    monkeypatch.setattr(projects.Project, "run_diff", lambda self: None)

    res = projects.Project.try_open(path)
    assert res is not None
    assert isinstance(res.rect, Rectangle)
