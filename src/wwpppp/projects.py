import pathlib
import re

from .geometry import Point
from .settings import DIRS

_RE_HAS_COORDS = re.compile(r"[^a-z0-9](\d+)[^a-z0-9](\d+)[^a-z0-9](\d+)[^a-z0-9](\d+)\.png$", flags=re.IGNORECASE)


class Project:
    def __init__(self, path: pathlib.Path, coords: tuple[str, str, str, str]):
        self.path = path
        self.coords = Point.from4(*(int(c) for c in coords))


def get_project_paths() -> list[Project]:
    results = []
    for path in DIRS.user_pictures_path.iterdir():
        match = _RE_HAS_COORDS.search(path.name)
        if match:
            results.append(Project(path, match.groups()))
    return results
