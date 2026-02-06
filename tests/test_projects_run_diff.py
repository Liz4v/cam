from pathlib import Path

from wwpppp import projects
from wwpppp.geometry import Point, Rectangle, Size
from wwpppp.palette import PALETTE


def _paletted_image(size=(4, 4), value=1):
    im = PALETTE.new(size)
    im.putdata([value] * (size[0] * size[1]))
    return im


def test_run_diff_complete_and_remaining(monkeypatch, tmp_path):
    # Prepare a project with a target image in memory
    rect = Rectangle.from_point_size(Point(0, 0), Size(4, 4))
    p = projects.Project(tmp_path / "proj_0_0_0_0.png", rect)

    target = _paletted_image((4, 4), value=1)
    p._image = target

    # Case: current equals target -> complete branch
    monkeypatch.setattr(projects, "stitch_tiles", lambda rect: _paletted_image((4, 4), value=1))
    p.run_diff()  # should hit the 'Complete.' branch without error

    # Case: current different -> remaining/progress calculation path
    monkeypatch.setattr(projects, "stitch_tiles", lambda rect: _paletted_image((4, 4), value=0))
    p.run_diff()  # should compute remaining and log progress without error


def test_project_image_property(tmp_path):
    # write an actual paletted file and exercise image property open and close
    path = tmp_path / "proj_0_0_0_0.png"
    im = _paletted_image((2, 2), value=2)
    im.save(path)

    rect = Rectangle.from_point_size(Point(0, 0), Size(2, 2))
    p = projects.Project(path, rect)
    img = p.image
    assert img.mode == "P"
    del p.image
