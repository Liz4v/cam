from pathlib import Path
from types import SimpleNamespace

from wwpppp import projects
from wwpppp.geometry import Point, Rectangle, Size


def test_pixel_compare():
    from wwpppp.projects import pixel_compare

    assert pixel_compare(1, 1) == 0
    assert pixel_compare(1, 2) == 2


def test_cached_project_metadata_call_and_load(tmp_path):
    # Prepare a fake DIRS so DB path is under tmp_path
    projects.DIRS = SimpleNamespace(user_cache_path=tmp_path, user_pictures_path=tmp_path)

    # Replace the _cursor classmethod with a fake cursor implementation
    storage = {}

    class FakeCursor:
        def __init__(self):
            self._last = None

        def execute(self, sql, params=()):
            sql = sql.strip().upper()
            if sql.startswith("SELECT"):
                key = params[0]
                row = storage.get(key)
                self._last = row
            elif sql.startswith("REPLACE"):
                key = params[0]
                storage[key] = (params[0], params[1], params[2], params[3], params[4], params[5])
                self._last = None
            elif sql.startswith("DELETE"):
                key = params[0]
                storage.pop(key, None)
                self._last = None
            elif sql.startswith("CREATE"):
                self._last = None
            elif sql.startswith("DROP"):
                storage.clear()
                self._last = None

        def fetchone(self):
            return self._last

    projects.CachedProjectMetadata._cursor = classmethod(lambda cls: FakeCursor())
    projects.CachedProjectMetadata._db = None

    # create a dummy file to get mtime
    p = tmp_path / "proj_0_0_0_0.png"
    p.write_bytes(b"ok")

    cached = projects.CachedProjectMetadata(p)
    assert list(cached) == []

    rect = Rectangle.from_point_size(Point(0, 0), Size(10, 10))
    cached(rect)
    # new cached object should load stored rect
    cached2 = projects.CachedProjectMetadata(p)
    assert list(cached2) == [rect]
