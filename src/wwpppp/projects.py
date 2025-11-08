import pathlib
import re

from PIL import Image

from .geometry import Point, Rectangle, Size
from .settings import DIRS

_RE_HAS_COORDS = re.compile(r"[^a-z0-9](\d+)[^a-z0-9](\d+)[^a-z0-9](\d+)[^a-z0-9](\d+)\.png$", flags=re.IGNORECASE)


class Project:
    def __init__(self, path: pathlib.Path, coords: tuple[str, str, str, str]):
        self.path = path
        with Image.open(path) as img:
            size = Size(*img.size)
        point = Point.from4(*map(int, coords))
        self.rect = Rectangle(point, size)


def get_project_paths() -> list[Project]:
    results = []
    for path in DIRS.user_pictures_path.iterdir():
        match = _RE_HAS_COORDS.search(path.name)
        if match:
            results.append(Project(path, match.groups()))
    return results
