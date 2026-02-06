from pathlib import Path
from types import SimpleNamespace

from wwpppp import projects
from wwpppp.geometry import Rectangle


def test_cached_project_metadata_db_lifecycle(tmp_path, monkeypatch):
    # monkeypatch DIRS to use tmp_path
    monkeypatch.setattr(projects, "DIRS", SimpleNamespace(user_cache_path=tmp_path, user_pictures_path=tmp_path))

    # ensure DB is created and table exists
    p = tmp_path / "proj_0_0_0_0.png"
    p.write_bytes(b"x")

    cp = projects.CachedProjectMetadata(p)
    assert list(cp) == []

    # create a rect and save via __call__
    rect = Rectangle(0, 0, 10, 10)
    cp(rect)

    # new instance should load the cached rect
    cp2 = projects.CachedProjectMetadata(p)
    assert list(cp2) == [rect]

    # forget should remove the cache
    cp2.forget()
    cp3 = projects.CachedProjectMetadata(p)
    assert list(cp3) == []
