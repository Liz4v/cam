import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from loguru import logger

from . import DIRS


class ProjectCacheDB:
    """Manages the projects.sqlite DB and provides a contextmanager cursor.

    Keeps connection and table-creation responsibilities outside of
    `CachedProjectMetadata` so that the metadata class remains focused
    on representing a single project's cached state.
    """

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir

    @contextmanager
    def cursor(self) -> Iterator[sqlite3.Cursor]:
        db_path = self.cache_dir
        db_path.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path / "projects.db", isolation_level=None)
        try:
            cur = conn.cursor()
            try:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS cache (
                        filename TEXT,
                        mtime INT,
                        left INT,
                        top INT,
                        right INT,
                        bottom INT,
                        PRIMARY KEY (filename)
                    )
                    """
                )
            except Exception:
                cur = conn.cursor()
            try:
                yield cur
                try:
                    conn.commit()
                except Exception:
                    pass
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
        except Exception:
            try:
                conn.close()
            except Exception:
                pass
            raise

    def reset_table(self) -> None:
        with self.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS cache")


# Module-level cache DB instance used by CachedProjectMetadata and callers
_CACHE_DB = ProjectCacheDB(DIRS.user_cache_path)
