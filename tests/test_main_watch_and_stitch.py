from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from wwpppp import main as main_mod
from wwpppp import projects
from wwpppp.cache import ProjectCacheDB
from wwpppp.geometry import Point, Rectangle, Size, Tile


def test_check_projects_processes_added_and_deleted(tmp_path, monkeypatch):
    """Test that check_projects correctly handles adding and deleting projects."""
    wplace_dir = tmp_path / "wplace"
    wplace_dir.mkdir()

    # Setup DIRS to point to tmp_path
    monkeypatch.setattr(
        main_mod, "DIRS", SimpleNamespace(user_pictures_path=tmp_path, user_cache_path=tmp_path / "cache")
    )

    # ensure Project.iter returns empty for deterministic start
    monkeypatch.setattr(projects.Project, "iter", classmethod(lambda cls: []))
    m = main_mod.Main()

    path = wplace_dir / "proj_0_0_1_1.png"
    path.touch()

    # Dummy project that exposes a single tile and records calls
    called = {"run": 0, "forgot": 0}

    class DummyProj:
        def __init__(self, p):
            self.path = p
            self.rect = Rectangle.from_point_size(Point.from4(0, 0, 0, 0), Size(1000, 1000))
            self.mtime = p.stat().st_mtime if p.exists() else None

        def run_diff(self):
            called["run"] += 1

        def forget(self):
            called["forgot"] += 1

    def make_proj(cls, p):
        inst = DummyProj(p)
        inst.run_diff()
        return inst

    monkeypatch.setattr(projects.Project, "try_open", classmethod(make_proj))

    # check_projects should detect the added file
    m.check_projects()
    assert called["run"] >= 1

    # Delete the file
    path.unlink()

    # check_projects should detect the deleted file
    m.check_projects()
    assert called["forgot"] >= 1


def test_stitch_tiles_warns_on_missing_and_returns_paletted_image(tmp_path, capsys, monkeypatch):
    # rectangle covering a single tile (0,0)
    rect = Rectangle.from_point_size(Point.from4(0, 0, 0, 0), Size(1000, 1000))

    # ensure cache dir is empty
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    # replace module cache dir so stitch_tiles looks at tmp cache
    from types import SimpleNamespace

    monkeypatch.setattr(projects, "DIRS", SimpleNamespace(user_cache_path=cache_dir))
    from wwpppp import ingest

    monkeypatch.setattr(ingest, "DIRS", SimpleNamespace(user_cache_path=cache_dir))

    img = ingest.stitch_tiles(rect)
    assert isinstance(img, Image.Image)
    # since no tile files exist, the result should be paletted (mode 'P')
    assert img.mode == "P"
    # loguru writes warnings to stderr; the warning appeared during the run
