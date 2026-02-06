from wwpppp.cache import ProjectCacheDB


def test_project_cache_db_basic(tmp_path):
    cache_dir = tmp_path / "cache"
    db = ProjectCacheDB(cache_dir)

    # Table is created on first cursor use
    with db.cursor() as cur:
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cache'")
        assert cur.fetchone() is not None

    # Insert a row and read it back
    with db.cursor() as cur:
        cur.execute(
            "INSERT OR REPLACE INTO cache VALUES (?, ?, ?, ?, ?, ?)",
            ("file.png", 123, 1, 2, 3, 4),
        )

    with db.cursor() as cur:
        cur.execute(
            "SELECT filename, mtime, left, top, right, bottom FROM cache WHERE filename = ?",
            ("file.png",),
        )
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "file.png"
        assert row[1] == 123

    # Reset the table and ensure it is recreated on next use
    db.reset_table()
    with db.cursor() as cur:
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cache'")
        assert cur.fetchone() is not None
