from pathlib import Path
from types import SimpleNamespace

import wwpppp.main as mainmod


def test_check_projects_handles_added_and_deleted(tmp_path, monkeypatch):
    """Test that check_projects correctly handles added and deleted project files."""
    wplace_dir = tmp_path / "wplace"
    wplace_dir.mkdir()

    # Setup DIRS to point to tmp_path
    monkeypatch.setattr(
        mainmod, "DIRS", SimpleNamespace(user_pictures_path=tmp_path, user_cache_path=tmp_path / "cache")
    )

    # create a fake project and Main instance
    proj_path = wplace_dir / "p_0_0_1_1.png"
    proj_path.touch()

    proj = SimpleNamespace(
        path=proj_path,
        rect=SimpleNamespace(tiles={}),
        run_diff=lambda: None,
        forget=lambda: None,
        mtime=proj_path.stat().st_mtime,
    )

    # monkeypatch Project as a class with classmethods
    class FakeProjectClass:
        @classmethod
        def iter(cls):
            return []

        @classmethod
        def try_open(cls, p):
            return proj

    monkeypatch.setattr(mainmod, "Project", FakeProjectClass)

    m = mainmod.Main()

    # check_projects should detect the new file
    m.check_projects()
    assert proj_path in m.projects

    # Delete the file
    proj_path.unlink()

    # check_projects should detect the deletion
    m.check_projects()
    assert proj_path not in m.projects
