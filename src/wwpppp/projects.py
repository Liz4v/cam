import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Optional, Self

from loguru import logger
from PIL import Image

from . import DIRS
from .cache import _CACHE_DB
from .geometry import Point, Rectangle, Size
from .ingest import stitch_tiles
from .palette import PALETTE, ColorNotInPalette

_RE_HAS_COORDS = re.compile(r"[- _](\d+)[- _](\d+)[- _](\d+)[- _](\d+)\.png$", flags=re.IGNORECASE)


class Project:
    """Represents a wplace project stored on disk."""

    @classmethod
    def iter(cls) -> Iterable[Self]:
        """Yields all valid projects found in the user pictures directory."""
        path = DIRS.user_pictures_path / "wplace"
        path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Searching for projects in {path}")
        maybe_projects = (cls.try_open(p) for p in sorted(path.iterdir()))
        return filter(None, maybe_projects)

    @classmethod
    def try_open(cls, path: Path) -> Optional[Self]:
        """Attempts to open a project from the given path. Returns None if invalid."""

        match = _RE_HAS_COORDS.search(path.name)
        if not match or not path.is_file():
            return None  # no coords or otherwise invalid/irrelevant

        cached = CachedProjectMetadata(path)
        if cached:
            try:
                return cls(path, *cached)
            except TypeError:
                logger.warning(f"{path.name}: Cache data invalid, reprocessing")

        try:
            # Convert now, but close immediately. We'll reopen later as needed.
            with PALETTE.open_image(path) as image:
                size = Size(*image.size)
        except ColorNotInPalette as e:
            logger.warning(f"{path.name}: Color not in palette: {e}")
            path.rename(path.with_suffix(".invalid.png"))
            return None
        rect = Rectangle.from_point_size(Point.from4(*map(int, match.groups())), size)

        logger.info(f"{path.name}: Detected project at {rect}")

        new = cls(path, *cached(rect))
        new.run_diff()
        return new

    def __init__(self, path: Path, rect: Rectangle):
        """Represents a wplace project stored at `path`, covering the area defined by `rect`."""
        self.path = path
        self.rect = rect
        self._image = None

    def __eq__(self, other) -> bool:
        return self.path == getattr(other, "path", ...)

    def __hash__(self):
        return hash(self.path)

    @property
    def image(self) -> Image.Image:
        """The target image for this project, lazy-opened as a PIL Image."""
        if self._image is None:
            self._image = PALETTE.open_image(self.path)
        return self._image

    @image.deleter
    def image(self) -> None:
        """Closes the cached image."""
        if self._image is not None:
            self._image.close()
            self._image = None

    def __del__(self):
        try:
            del self.image
        except Exception:
            pass

    def run_diff(self) -> None:
        """Compares each pixel between both images. Generates a new image only with the differences."""

        target_data = self.image.get_flattened_data()
        with stitch_tiles(self.rect) as current:
            newdata = map(pixel_compare, current.get_flattened_data(), target_data)  # type: ignore[misc]
            remaining = bytes(newdata)

        if remaining == target_data:
            return  # project is not started, no need for diffs

        if max(remaining) == 0:
            logger.info(f"{self.path.name}: Complete.")
            return

        num_remaining = sum(1 for v in remaining if v)
        num_target = sum(1 for v in target_data if v) or 1  # avoid div by 0
        percentage = num_remaining * 100 / num_target
        time_to_go = timedelta(seconds=27) * num_remaining
        days, hours = divmod(round(time_to_go.total_seconds() / 3600), 24)
        when = (datetime.now() + time_to_go).strftime("%b %d %H:%M")
        logger.info(f"{self.path.name} remaining: {num_remaining}px, {percentage:.2f}%, {days}d{hours}h to {when}.")

    def forget(self) -> None:
        """Deletes cached metadata about this project."""
        cached = CachedProjectMetadata(self.path)
        cached.forget()


def pixel_compare(current: int, desired: int) -> int:
    """Returns the desired pixel value if it differs from the current pixel, otherwise returns transparent."""
    return 0 if desired == current else desired


class CachedProjectMetadata(list):
    """Caches metadata about a project in a local SQLite database.

    Uses a short-lived connection per operation to avoid leaving a global
    connection open across the process lifetime.
    """

    @classmethod
    def _cursor(cls):
        """Compatibility passthrough to the shared cache DB cursor contextmanager."""
        return _CACHE_DB.cursor()

    @classmethod
    def _reset_table(cls) -> None:
        logger.error("Cache table seems malformed or out of date. Resetting.")
        _CACHE_DB.reset_table()

    def __init__(self, path: Path):
        """Loads cached metadata for the project at `path`."""
        self.key = path.name
        try:
            self.mtime = int(path.stat().st_mtime)
        except FileNotFoundError:
            self.mtime = 0  # signal missing file
        super().__init__(self._load())

    def _load(self) -> list:
        """Loads cached metadata from the database, if valid."""
        cm = self._cursor()
        if hasattr(cm, "__enter__"):
            with cm as cursor:
                cursor.execute("SELECT * FROM cache WHERE filename = ? ", (self.key,))
                row = cursor.fetchone()
        else:
            cursor = cm
            cursor.execute("SELECT * FROM cache WHERE filename = ? ", (self.key,))
            row = cursor.fetchone()
        if not row:
            return []
        try:
            _, mtime, left, top, right, bottom = row
        except ValueError:
            self._reset_table()
            return []
        if mtime != self.mtime:
            return []
        return [Rectangle(left, top, right, bottom)]

    def __call__(self, rect: Rectangle) -> list:
        """Saves a new cached metadata for this project."""
        cm = self._cursor()
        if hasattr(cm, "__enter__"):
            with cm as cursor:
                cursor.execute(
                    "REPLACE INTO cache VALUES (?, ?, ?, ?, ?, ?)",
                    (self.key, self.mtime, rect.left, rect.top, rect.right, rect.bottom),
                )
        else:
            cm.execute(
                "REPLACE INTO cache VALUES (?, ?, ?, ?, ?, ?)",
                (self.key, self.mtime, rect.left, rect.top, rect.right, rect.bottom),
            )
        self.clear()
        self.append(rect)
        return self

    def forget(self) -> None:
        """Deletes cached metadata for this project."""
        cm = self._cursor()
        if hasattr(cm, "__enter__"):
            with cm as cursor:
                cursor.execute("DELETE FROM cache WHERE filename = ?", (self.key,))
        else:
            cm.execute("DELETE FROM cache WHERE filename = ?", (self.key,))
