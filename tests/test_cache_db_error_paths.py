import sqlite3

from wwpppp.cache import ProjectCacheDB


def test_cursor_handles_table_creation_error(monkeypatch, tmp_path):
    """Simulate an error during CREATE TABLE and ensure cursor still yields."""

    class FakeCursor:
        def __init__(self):
            self._first = True

        def execute(self, sql, params=None):
            # raise on the first CREATE TABLE attempt
            if self._first and "CREATE TABLE" in sql:
                self._first = False
                raise Exception("boom")
            return None

        def fetchone(self):
            return None

    class FakeConn:
        def __init__(self):
            self._cursor = FakeCursor()

        def cursor(self):
            return self._cursor

        def commit(self):
            return None

        def close(self):
            return None

    def fake_connect(path, isolation_level=None):
        return FakeConn()

    monkeypatch.setattr(sqlite3, "connect", fake_connect)

    db = ProjectCacheDB(tmp_path / "cache")

    with db.cursor() as cur:
        # should not raise, even though CREATE TABLE raised once internally
        cur.execute("SELECT 1")
