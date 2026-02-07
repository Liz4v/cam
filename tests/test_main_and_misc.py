from pathlib import Path
from types import SimpleNamespace

from wwpppp import main as main_mod
from wwpppp import projects
from wwpppp.cache import ProjectCacheDB
from wwpppp.geometry import Tile


def test_main_indexing_and_check_tiles_and_load_forget(tmp_path, monkeypatch):
    # start with no projects
    monkeypatch.setattr(projects.Project, "iter", classmethod(lambda cls: []))
    m = main_mod.Main()
    assert m.tiles == {}

    # create dummy project returned by try_open
    path = tmp_path / "proj_0_0_1_1.png"
    path.touch()

    called = {}

    class DummyProj:
        def __init__(self, path):
            self.path = path
            self.rect = SimpleNamespace(tiles=frozenset({Tile(0, 0)}))

        def run_diff(self):
            called["run"] = True

        def forget(self):
            called["forgot"] = True

    monkeypatch.setattr(projects.Project, "try_open", classmethod(lambda cls, p: DummyProj(p)))

    m.load_project(path)
    assert path in m.projects
    assert Tile(0, 0) in m.tiles

    # check_tiles with has_tile_changed returning True should call run_diff
    monkeypatch.setattr(main_mod, "has_tile_changed", lambda tile: True)
    m.check_tiles()
    assert called.get("run") is True

    # forget should remove project and call forget
    m.forget_project(path)
    assert path not in m.projects
    assert called.get("forgot") is True


def test_check_projects_detects_added_and_deleted(tmp_path, monkeypatch):
    """Test that check_projects detects added and deleted project files."""
    wplace_dir = tmp_path / "wplace"
    wplace_dir.mkdir()

    # Setup DIRS to point to tmp_path
    monkeypatch.setattr(
        main_mod, "DIRS", SimpleNamespace(user_pictures_path=tmp_path, user_cache_path=tmp_path / "cache")
    )

    # Start with no projects
    monkeypatch.setattr(projects.Project, "iter", classmethod(lambda cls: []))
    m = main_mod.Main()

    # Track calls to load_project and forget_project
    loaded = []
    forgotten = []
    original_load = m.load_project
    original_forget = m.forget_project

    def track_load(p):
        loaded.append(p)
        original_load(p)

    def track_forget(p):
        forgotten.append(p)
        original_forget(p)

    m.load_project = track_load
    m.forget_project = track_forget

    # Create a new project file
    proj_path = wplace_dir / "proj_0_0_1_1.png"
    proj_path.touch()

    # Mock Project.try_open to return a dummy project
    class DummyProj:
        def __init__(self, path):
            self.path = path
            self.rect = SimpleNamespace(tiles=frozenset())

        def run_diff(self):
            pass

        def forget(self):
            pass

    monkeypatch.setattr(projects.Project, "try_open", classmethod(lambda cls, p: DummyProj(p)))

    # check_projects should detect the new file
    m.check_projects()
    assert proj_path in loaded

    # Delete the project file
    proj_path.unlink()

    # check_projects should detect the deletion
    loaded.clear()
    m.check_projects()
    assert proj_path in forgotten


def test_palette_lookup_transparent_and_ensure():
    # transparent pixel should map to 0
    idx = projects.PALETTE.lookup((0, 0, 0, 0))
    assert idx == 0


def test_has_tile_changed_http_error(monkeypatch):
    from wwpppp.ingest import has_tile_changed

    class FakeResp:
        status_code = 404

    monkeypatch.setattr("requests.get", lambda url, timeout=5: FakeResp())

    assert has_tile_changed(Tile(0, 0)) is False


def test_run_forever_handles_keyboard_interrupt(monkeypatch):
    """Test that run_forever handles KeyboardInterrupt gracefully."""
    monkeypatch.setattr(projects.Project, "iter", classmethod(lambda cls: []))
    m = main_mod.Main()

    # Make check_tiles and check_projects raise KeyboardInterrupt after first call
    call_count = {"count": 0}

    def fake_check_tiles():
        call_count["count"] += 1
        if call_count["count"] > 0:
            raise KeyboardInterrupt

    m.check_tiles = fake_check_tiles
    m.check_projects = lambda: None

    # run_forever should catch KeyboardInterrupt and exit gracefully
    m.run_forever()  # Should not raise


def test_cache_cursor_outer_exception_closes(monkeypatch, tmp_path):
    # Simulate conn.cursor() raising to exercise outer except block
    class BadConn:
        def cursor(self):
            raise Exception("boom")

        def close(self):
            # closing shouldn't raise
            return None

    def fake_connect(path, isolation_level=None):
        return BadConn()

    monkeypatch.setattr("sqlite3.connect", fake_connect)
    db = ProjectCacheDB(tmp_path / "cache")
    import pytest

    with pytest.raises(Exception):
        with db.cursor():
            pass
