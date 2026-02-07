import time
from pathlib import Path

from loguru import logger

from . import DIRS
from .geometry import Tile
from .ingest import has_tile_changed
from .projects import Project


class Main:
    def __init__(self):
        """Initialize the main application, loading existing projects and indexing tiles."""
        self.projects = {p.path: p for p in Project.iter()}
        logger.info(f"Loaded {len(self.projects)} projects.")
        self.tiles = self._load_tiles()

    def _load_tiles(self) -> dict[Tile, set[Project]]:
        """Index tiles to projects for quick lookup."""
        tile_to_project = {}
        for proj in self.projects.values():
            for tile in proj.rect.tiles:
                tile_to_project.setdefault(tile, set()).add(proj)
        logger.info(f"Indexed {len(tile_to_project)} tiles.")
        return tile_to_project

    def check_tiles(self) -> None:
        """Check all tiles for changes and update affected projects."""
        for tile in list(self.tiles.keys()):
            if has_tile_changed(tile):
                for proj in self.tiles.get(tile) or ():
                    proj.run_diff()

    def check_projects(self) -> None:
        """Check projects directory for added, modified, or deleted files."""
        wplace_path = DIRS.user_pictures_path / "wplace"
        wplace_path.mkdir(parents=True, exist_ok=True)

        # Get current files from disk
        current_files = {p for p in wplace_path.glob("*.png") if p.is_file()}
        known_files = set(self.projects.keys())

        # Handle deleted files
        deleted = known_files - current_files
        for path in deleted:
            self.forget_project(path)

        # Handle new and potentially modified files
        for path in current_files:
            if path in deleted:
                continue
            # Load/reload all current files to catch modifications
            if path not in known_files or self._file_modified(path):
                self.load_project(path)

    def _file_modified(self, path: Path) -> bool:
        """Check if a project file has been modified since it was loaded."""
        proj = self.projects.get(path)
        if not proj:
            return True
        try:
            current_mtime = path.stat().st_mtime
            return current_mtime != getattr(proj, "mtime", None)
        except OSError:
            return True

    def run_forever(self) -> None:
        """Run the main polling loop, checking tiles and projects every two minutes."""
        logger.info("Starting polling loop (~2-minute cycle)...")
        try:
            while True:
                logger.debug("Checking for tile updates...")
                self.check_tiles()
                logger.debug("Checking for project file changes...")
                self.check_projects()
                logger.debug("Cycle complete, sleeping for 120 seconds...")
                time.sleep(127)  # we want a little bit of drift to avoid always hitting the same time on the minute
        except KeyboardInterrupt:
            logger.info("Interrupted by user.")

    def forget_project(self, path: Path) -> None:
        """Clears cached data about the project at the given path."""
        proj = self.projects.pop(path, None)
        if not proj:
            return
        for tile in proj.rect.tiles:
            projs = self.tiles.get(tile)
            if projs:
                projs.discard(proj)
                if not projs:
                    del self.tiles[tile]
        logger.info(f"{path.name}: Forgot project")

    def load_project(self, path: Path) -> None:
        """Loads or reloads a project at the given path."""
        self.forget_project(path)
        proj = Project.try_open(path)
        if not proj:
            return
        self.projects[path] = proj
        for tile in proj.rect.tiles:
            self.tiles.setdefault(tile, set()).add(proj)
        logger.info(f"{path.name}: Loaded project")


def main():
    """Main entry point for wwpppp."""
    worker = Main()
    worker.run_forever()
    logger.info("Exiting.")


if __name__ == "__main__":
    main()
