from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from wwpppp import projects
from wwpppp.geometry import Point, Rectangle, Size
from wwpppp.palette import PALETTE, ColorNotInPalette


def _paletted_image(size=(4, 4), value=1):
    """Helper to create a paletted image for testing."""
    im = PALETTE.new(size)
    im.putdata([value] * (size[0] * size[1]))
    return im


# Basic utility tests


def test_pixel_compare():
    from wwpppp.projects import pixel_compare

    assert pixel_compare(1, 1) == 0
    assert pixel_compare(1, 2) == 2


# Project.try_open tests


def test_try_open_no_coords(tmp_path):
    """Test that try_open returns None when filename has no coordinates."""
    p = tmp_path / "no_coords.png"
    p.write_bytes(b"x")
    assert projects.Project.try_open(p) is None


def test_try_open_invalid_color(tmp_path, monkeypatch):
    """Test that try_open renames files with invalid palette colors."""
    # write an image with a color not in the palette
    path = tmp_path / "proj_0_0_0_0.png"
    im = Image.new("RGBA", (2, 2), (250, 251, 252, 255))
    im.save(path)

    # try_open should detect color not in palette and rename the file
    res = projects.Project.try_open(path)
    assert res is None
    assert path.with_suffix(".invalid.png").exists()


def test_try_open_valid_project_and_run_diff(tmp_path, monkeypatch):
    """Test that try_open successfully opens a valid project file."""
    # create a correct paletted image
    path = tmp_path / "proj_1_1_0_0.png"
    im = PALETTE.new((10, 10))
    im.putdata([1] * 100)
    im.save(path)

    # monkeypatch stitch_tiles to return identical image -> run_diff should be quick
    monkeypatch.setattr(projects, "stitch_tiles", lambda rect: PALETTE.new((10, 10)))
    # avoid heavy logging or side effects
    monkeypatch.setattr(projects.Project, "run_diff", lambda self: None)

    res = projects.Project.try_open(path)
    assert res is not None
    assert isinstance(res.rect, Rectangle)


# Project.run_diff tests


def test_run_diff_branches(monkeypatch, tmp_path):
    """Test run_diff with various scenarios (no change, changes)."""
    # create a dummy project and exercise run_diff branches
    p = tmp_path / "proj_0_0_1_1.png"
    p.touch()
    rect = Rectangle.from_point_size(Point.from4(0, 0, 0, 0), Size(1, 1))
    proj = projects.Project(p, rect)

    class DummyImage:
        def __init__(self, data):
            self._data = data

        def get_flattened_data(self):
            return self._data

        def close(self):
            pass

    # Case 1: no change (current == target)
    target = bytes([1, 2, 3])
    proj._image = DummyImage(target)

    class CM:
        def __init__(self, data):
            self.data = data

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get_flattened_data(self):
            return self.data

    monkeypatch.setattr(projects, "stitch_tiles", lambda rect: CM(target))
    proj.run_diff()  # should early-return without error

    # Case 2: progress branch (different data)
    proj._image = DummyImage(bytes([0, 1, 2]))
    monkeypatch.setattr(projects, "stitch_tiles", lambda rect: CM(bytes([2, 3, 4])))
    proj.run_diff()  # should run through progress logging


def test_run_diff_complete_and_remaining(monkeypatch, tmp_path):
    """Test run_diff complete and progress calculation paths."""
    # Create the file first so Project.__init__ doesn't fail
    proj_path = tmp_path / "proj_0_0_0_0.png"
    proj_path.touch()

    # Prepare a project with a target image in memory
    rect = Rectangle.from_point_size(Point(0, 0), Size(4, 4))
    p = projects.Project(proj_path, rect)

    target = _paletted_image((4, 4), value=1)
    p._image = target

    # Case: current equals target -> complete branch
    monkeypatch.setattr(projects, "stitch_tiles", lambda rect: _paletted_image((4, 4), value=1))
    p.run_diff()  # should hit the 'Complete.' branch without error

    # Case: current different -> remaining/progress calculation path
    monkeypatch.setattr(projects, "stitch_tiles", lambda rect: _paletted_image((4, 4), value=0))
    p.run_diff()  # should compute remaining and log progress without error


# Project property tests


def test_project_image_property(tmp_path):
    """Test the image property opens/closes correctly."""
    # write an actual paletted file and exercise image property open and close
    path = tmp_path / "proj_0_0_0_0.png"
    im = _paletted_image((2, 2), value=2)
    im.save(path)

    rect = Rectangle.from_point_size(Point(0, 0), Size(2, 2))
    p = projects.Project(path, rect)
    img = p.image
    assert img.mode == "P"
    del p.image
