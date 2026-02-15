import time

from PIL import Image

from pixel_hawk import projects
from pixel_hawk.geometry import Point, Rectangle, Size
from pixel_hawk.metadata import ProjectMetadata
from pixel_hawk.palette import PALETTE, AsyncImage


def _paletted_image(size=(4, 4), value=1):
    """Helper to create a paletted image for testing."""
    im = PALETTE.new(size)
    im.putdata([value] * (size[0] * size[1]))
    return im


class FakeAsyncImage:
    """Mock AsyncImage for tests that need to patch aopen_file."""

    def __init__(self, image):
        self._image = image

    async def __aenter__(self):
        return self._image

    async def __aexit__(self, *_):
        pass

    async def __call__(self):
        return self._image


# Basic utility tests


# Project.try_open tests


async def test_try_open_no_coords(tmp_path, setup_config):
    """Test that try_open returns None and moves file to rejected/ when filename has no coordinates."""
    p = setup_config.projects_dir / "no_coords.png"
    p.write_bytes(b"x")
    result = await projects.Project.try_open(p)
    assert result is None
    assert not p.exists()
    assert (setup_config.rejected_dir / "no_coords.png").exists()


async def test_try_open_invalid_color(tmp_path, setup_config):
    """Test that try_open moves files with invalid palette colors to rejected/."""
    path = setup_config.projects_dir / "proj_0_0_0_0.png"
    im = Image.new("RGBA", (2, 2), (250, 251, 252, 255))
    im.save(path)

    res = await projects.Project.try_open(path)
    assert res is None
    assert not path.exists()
    assert (setup_config.rejected_dir / "proj_0_0_0_0.png").exists()


async def test_try_open_valid_project_and_run_diff(tmp_path, monkeypatch):
    """Test that try_open successfully opens a valid project file."""
    # create a correct paletted image
    path = tmp_path / "proj_1_1_0_0.png"
    im = PALETTE.new((10, 10))
    im.putdata([1] * 100)
    im.save(path)

    # monkeypatch run_diff to avoid needing stitch_tiles
    async def noop_run_diff(self, changed_tile=None):
        pass

    monkeypatch.setattr(projects.Project, "run_diff", noop_run_diff)

    res = await projects.Project.try_open(path)
    assert isinstance(res, projects.Project)
    assert isinstance(res.rect, Rectangle)


# Project.run_diff tests


async def test_run_diff_branches(monkeypatch, tmp_path):
    """Test run_diff with various scenarios (no change, changes)."""
    # create a dummy project and exercise run_diff branches
    p = tmp_path / "proj_0_0_1_1.png"
    p.touch()
    rect = Rectangle.from_point_size(Point.from4(0, 0, 0, 0), Size(1, 1))
    proj = projects.Project(p, rect)

    class DummyImage:
        def __init__(self, data):
            self._data = data

        def get_flattened_data(self):
            return self._data

        def close(self):
            pass

    # Case 1: no change (current == target)
    target = bytes([1, 2, 3])

    class CM:
        def __init__(self, data):
            self.data = data
            self.size = (1, 1)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get_flattened_data(self):
            return self.data

        def save(self, path):
            pass

        def close(self):
            pass

    monkeypatch.setattr(PALETTE, "aopen_file", lambda path: FakeAsyncImage(CM(target)))

    async def fake_stitch(rect):
        return CM(target)

    monkeypatch.setattr(projects, "stitch_tiles", fake_stitch)
    await proj.run_diff()  # should early-return without error

    # Case 2: progress branch (different data)
    monkeypatch.setattr(PALETTE, "aopen_file", lambda path: FakeAsyncImage(CM(bytes([0, 1, 2]))))

    async def fake_stitch2(rect):
        return CM(bytes([2, 3, 4]))

    monkeypatch.setattr(projects, "stitch_tiles", fake_stitch2)
    await proj.run_diff()  # should run through progress logging


async def test_run_diff_complete_and_remaining(monkeypatch, tmp_path):
    """Test run_diff complete and progress calculation paths."""
    # Create the file first so Project.__init__ doesn't fail
    proj_path = tmp_path / "proj_0_0_0_0.png"
    proj_path.touch()

    # Prepare a project with a target image in memory
    rect = Rectangle.from_point_size(Point(0, 0), Size(4, 4))
    p = projects.Project(proj_path, rect)

    target = _paletted_image((4, 4), value=1)

    # Case: current equals target -> complete branch
    monkeypatch.setattr(PALETTE, "aopen_file", lambda path: FakeAsyncImage(target))

    async def fake_stitch_complete(rect):
        return _paletted_image((4, 4), value=1)

    monkeypatch.setattr(projects, "stitch_tiles", fake_stitch_complete)
    await p.run_diff()  # should hit the 'Complete.' branch without error

    # Case: current different -> remaining/progress calculation path
    monkeypatch.setattr(PALETTE, "aopen_file", lambda path: FakeAsyncImage(target))

    async def fake_stitch_partial(rect):
        return _paletted_image((4, 4), value=0)

    monkeypatch.setattr(projects, "stitch_tiles", fake_stitch_partial)
    await p.run_diff()  # should compute remaining and log progress without error


async def test_try_open_non_file(tmp_path, setup_config):
    """Test that try_open returns None for directories and non-files."""
    d = tmp_path / "not_a_file_0_0_0_0.png"
    d.mkdir()
    result = await projects.Project.try_open(d)
    assert result is None


async def test_project_first_seen(tmp_path, setup_config, monkeypatch):
    """Test that Project.metadata.first_seen is set on creation."""
    # Create a valid project file in projects_dir
    path = setup_config.projects_dir / "proj_0_0_0_0.png"

    # Create a paletted image
    img = PALETTE.new((4, 4))
    img.save(path)

    # Mock run_diff to avoid needing stitch_tiles
    async def noop_run_diff(self, changed_tile=None):
        pass

    monkeypatch.setattr(projects.Project, "run_diff", noop_run_diff)

    # Open as project
    proj = await projects.Project.try_open(path)

    # Should be a valid Project
    assert isinstance(proj, projects.Project)

    # metadata.first_seen should be set
    assert proj.metadata.first_seen > 0


# Project.scan_directory tests


async def test_scan_directory(tmp_path, setup_config):
    """Test Project.scan_directory returns PNG files."""
    # setup_config already creates projects_dir, just use it
    projects_dir = setup_config.projects_dir

    # Create some files
    png1 = projects_dir / "file1.png"
    png2 = projects_dir / "file2.png"
    txt = projects_dir / "file.txt"
    png1.touch()
    png2.touch()
    txt.touch()

    result = await projects.Project.scan_directory()
    assert png1 in result
    assert png2 in result
    assert txt not in result
    assert len(result) == 2


# Project.has_been_modified tests


def test_project_has_been_modified(tmp_path):
    """Test Project.has_been_modified detects file changes."""
    path = tmp_path / "proj_0_0_0_0.png"
    im = _paletted_image((2, 2), value=1)
    im.save(path)

    rect = Rectangle.from_point_size(Point(0, 0), Size(2, 2))
    proj = projects.Project(path, rect)

    # Should not be modified right after creation
    assert not proj.has_been_modified()

    # Manually set mtime to a different value to simulate passage of time
    real_mtime = round(path.stat().st_mtime)
    proj.mtime = real_mtime - 1  # Set to 1 second earlier

    # Should detect modification
    assert proj.has_been_modified()


def test_project_has_been_modified_with_oserror(tmp_path):
    """Test Project.has_been_modified handles OSError."""
    path = tmp_path / "proj_0_0_0_0.png"
    im = _paletted_image((2, 2), value=1)
    im.save(path)

    rect = Rectangle.from_point_size(Point(0, 0), Size(2, 2))
    proj = projects.Project(path, rect)

    # Delete the file
    path.unlink()

    # Should return True when stat fails
    assert proj.has_been_modified()


def test_project_has_been_modified_with_none_mtime(tmp_path):
    """Test Project.has_been_modified when mtime is None."""
    path = tmp_path / "proj_0_0_0_0.png"
    im = _paletted_image((2, 2), value=1)
    im.save(path)

    rect = Rectangle.from_point_size(Point(0, 0), Size(2, 2))
    proj = projects.Project(path, rect)
    proj.mtime = 0

    # Should return True when mtime is None
    assert proj.has_been_modified()


def test_project_equality_and_hash(tmp_path):
    """Test Project __eq__ and __hash__ methods."""
    path1 = tmp_path / "proj_0_0_0_0.png"
    path2 = tmp_path / "proj_1_1_1_1.png"

    im = _paletted_image((2, 2), value=1)
    im.save(path1)
    im.save(path2)

    rect = Rectangle.from_point_size(Point(0, 0), Size(2, 2))
    proj1 = projects.Project(path1, rect)
    proj2 = projects.Project(path1, rect)  # same path
    proj3 = projects.Project(path2, rect)  # different path

    # Same path should be equal
    assert proj1 == proj2
    assert hash(proj1) == hash(proj2)

    # Different paths should not be equal
    assert proj1 != proj3
    assert hash(proj1) != hash(proj3)

    # Equality with non-Project object
    assert proj1 != "not a project"


def test_project_deletion(tmp_path):
    """Test Project deletion does not raise."""
    path = tmp_path / "proj_0_0_0_0.png"
    im = _paletted_image((2, 2), value=1)
    im.save(path)

    rect = Rectangle.from_point_size(Point(0, 0), Size(2, 2))
    proj = projects.Project(path, rect)

    # Delete the project - should not raise
    del proj


# ProjectMetadata tests


def test_metadata_from_rect():
    """Test ProjectMetadata.from_rect creates correct initial state."""
    rect = Rectangle.from_point_size(Point(100, 200), Size(50, 60))
    meta = ProjectMetadata.from_rect(rect, "test.png")

    assert meta.name == "test.png"
    assert meta.x == 100
    assert meta.y == 200
    assert meta.width == 50
    assert meta.height == 60
    assert meta.first_seen > 0
    assert meta.last_check > 0
    assert meta.max_completion_pixels == 0
    assert meta.total_progress == 0
    assert meta.total_regress == 0


def test_metadata_to_dict_and_from_dict():
    """Test metadata serialization round-trip."""
    rect = Rectangle.from_point_size(Point(10, 20), Size(30, 40))
    meta = ProjectMetadata.from_rect(rect, "project.png")
    meta.max_completion_pixels = 100
    meta.max_completion_percent = 75.5
    meta.total_progress = 50
    meta.total_regress = 5
    meta.tile_last_update = {"1_2": 12345, "3_4": 67890}
    meta.tile_updates_24h = [("1_2", 12345), ("3_4", 67890)]

    data = meta.to_dict()
    meta2 = ProjectMetadata.from_dict(data)

    assert meta2.x == meta.x
    assert meta2.y == meta.y
    assert meta2.width == meta.width
    assert meta2.height == meta.height
    assert meta2.max_completion_pixels == meta.max_completion_pixels
    assert meta2.max_completion_percent == meta.max_completion_percent
    assert meta2.total_progress == meta.total_progress
    assert meta2.total_regress == meta.total_regress
    assert meta2.tile_last_update == meta.tile_last_update
    assert meta2.tile_updates_24h == meta.tile_updates_24h


def test_metadata_prune_old_tile_updates():
    """Test pruning of old tile updates from 24h list."""
    meta = ProjectMetadata()
    now = round(time.time())
    old_time = now - 100000  # more than 24h ago
    recent_time = now - 1000  # within 24h

    meta.tile_updates_24h = [
        ("1_2", old_time),
        ("3_4", recent_time),
        ("5_6", old_time),
        ("7_8", recent_time),
    ]

    meta.last_check = now
    meta.prune_old_tile_updates()

    assert len(meta.tile_updates_24h) == 2
    assert ("3_4", recent_time) in meta.tile_updates_24h
    assert ("7_8", recent_time) in meta.tile_updates_24h
    assert ("1_2", old_time) not in meta.tile_updates_24h


def test_metadata_update_tile():
    """Test tile update recording."""
    from pixel_hawk.geometry import Tile

    meta = ProjectMetadata()
    tile = Tile(1, 2)
    timestamp = 12345

    meta.update_tile(tile, timestamp)

    assert meta.tile_last_update["1_2"] == timestamp
    assert ("1_2", timestamp) in meta.tile_updates_24h

    # Update same tile with new timestamp
    new_timestamp = 67890
    meta.update_tile(tile, new_timestamp)

    assert meta.tile_last_update["1_2"] == new_timestamp
    assert ("1_2", new_timestamp) in meta.tile_updates_24h


def test_project_metadata_paths(tmp_path, setup_config):
    """Test snapshot_path and metadata_path properties."""
    path = tmp_path / "proj_0_0_0_0.png"
    path.touch()
    rect = Rectangle.from_point_size(Point(0, 0), Size(2, 2))
    proj = projects.Project(path, rect)

    # Paths should now be in config's snapshots_dir and metadata_dir
    assert proj.snapshot_path == setup_config.snapshots_dir / "proj_0_0_0_0.snapshot.png"
    assert proj.metadata_path == setup_config.metadata_dir / "proj_0_0_0_0.metadata.yaml"


def test_project_metadata_save_and_load(tmp_path):
    """Test metadata persistence to YAML file."""
    path = tmp_path / "proj_0_0_0_0.png"
    im = _paletted_image((2, 2), value=1)
    im.save(path)
    rect = Rectangle.from_point_size(Point(0, 0), Size(2, 2))
    proj = projects.Project(path, rect)

    # Modify metadata
    proj.metadata.max_completion_pixels = 42
    proj.metadata.total_progress = 100

    # Save metadata
    proj.save_metadata()
    assert proj.metadata_path.exists()

    # Create new project instance and verify metadata loaded
    proj2 = projects.Project(path, rect)
    assert proj2.metadata.max_completion_pixels == 42
    assert proj2.metadata.total_progress == 100


async def test_project_snapshot_save_and_load(tmp_path, monkeypatch):
    """Test snapshot persistence."""
    path = tmp_path / "proj_0_0_0_0.png"
    im = _paletted_image((4, 4), value=1)
    im.save(path)
    rect = Rectangle.from_point_size(Point(0, 0), Size(4, 4))
    proj = projects.Project(path, rect)

    # Create and save a snapshot
    snapshot = _paletted_image((4, 4), value=2)
    await proj.save_snapshot(snapshot)
    assert proj.snapshot_path.exists()
    assert proj.metadata.last_snapshot > 0

    # Load snapshot and verify
    async with proj.load_snapshot_if_exists() as loaded:
        assert loaded is not None
        data = loaded.get_flattened_data()
        assert all(v == 2 for v in data)


async def test_project_snapshot_load_nonexistent(tmp_path):
    """Test loading snapshot when it doesn't exist."""
    path = tmp_path / "proj_0_0_0_0.png"
    im = _paletted_image((2, 2), value=1)
    im.save(path)
    rect = Rectangle.from_point_size(Point(0, 0), Size(2, 2))
    proj = projects.Project(path, rect)

    async with proj.load_snapshot_if_exists() as snapshot:
        assert snapshot is None


async def test_run_diff_with_metadata_tracking(tmp_path, monkeypatch):
    """Test that run_diff updates metadata correctly."""
    path = tmp_path / "proj_0_0_0_0.png"
    path.touch()
    rect = Rectangle.from_point_size(Point(0, 0), Size(4, 4))
    proj = projects.Project(path, rect)

    # Setup: target has some pixels set
    target = _paletted_image((4, 4), value=0)
    target.putpixel((0, 0), 1)
    target.putpixel((1, 1), 2)
    target.putpixel((2, 2), 3)

    # Current state: partial progress (1 pixel correct, 2 wrong)
    current = _paletted_image((4, 4), value=0)
    current.putpixel((0, 0), 1)  # correct

    monkeypatch.setattr(PALETTE, "aopen_file", lambda path_arg: FakeAsyncImage(target))

    async def fake_stitch(rect_arg):
        return current

    monkeypatch.setattr(projects, "stitch_tiles", fake_stitch)

    await proj.run_diff()

    # Check metadata was updated
    assert proj.metadata.last_check > 0
    assert proj.metadata.max_completion_pixels > 0
    assert proj.metadata.max_completion_percent > 0
    assert proj.snapshot_path.exists()


async def test_run_diff_progress_and_regress_tracking(tmp_path, monkeypatch):
    """Test progress/regress detection between checks."""
    path = tmp_path / "proj_0_0_0_0.png"
    path.touch()
    rect = Rectangle.from_point_size(Point(0, 0), Size(4, 4))
    proj = projects.Project(path, rect)

    # Target: pixels (0,0)=1, (1,1)=2
    target = _paletted_image((4, 4), value=0)
    target.putpixel((0, 0), 1)
    target.putpixel((1, 1), 2)

    # First check: (0,0) correct
    current1 = _paletted_image((4, 4), value=0)
    current1.putpixel((0, 0), 1)

    # aopen_file mock: use real PALETTE.open_file for snapshots, fake for project
    original_open_file = PALETTE.open_file

    def aopen_file_mock(path_arg):
        if ".snapshot." in str(path_arg):
            return AsyncImage(original_open_file, path_arg)
        return FakeAsyncImage(target)

    monkeypatch.setattr(PALETTE, "aopen_file", aopen_file_mock)

    async def fake_stitch1(rect_arg):
        return current1

    monkeypatch.setattr(projects, "stitch_tiles", fake_stitch1)

    await proj.run_diff()
    initial_progress = proj.metadata.total_progress

    # Second check: (0,0) still correct, (1,1) now correct too (progress)
    current2 = _paletted_image((4, 4), value=0)
    current2.putpixel((0, 0), 1)
    current2.putpixel((1, 1), 2)

    async def fake_stitch2(rect_arg):
        return current2

    monkeypatch.setattr(projects, "stitch_tiles", fake_stitch2)

    await proj.run_diff()

    # Should have detected 1 pixel of progress
    assert proj.metadata.total_progress == initial_progress + 1


async def test_run_diff_regress_detection(tmp_path, monkeypatch):
    """Test regress (griefing) detection."""
    path = tmp_path / "proj_0_0_0_0.png"
    path.touch()
    rect = Rectangle.from_point_size(Point(0, 0), Size(4, 4))
    proj = projects.Project(path, rect)

    # Target: pixel (0,0)=1
    target = _paletted_image((4, 4), value=0)
    target.putpixel((0, 0), 1)

    # First check: (0,0) correct
    current1 = _paletted_image((4, 4), value=0)
    current1.putpixel((0, 0), 1)

    monkeypatch.setattr(PALETTE, "aopen_file", lambda path_arg: FakeAsyncImage(target))

    async def fake_stitch1(rect_arg):
        return current1

    monkeypatch.setattr(projects, "stitch_tiles", fake_stitch1)

    await proj.run_diff()

    # Second check: (0,0) now wrong (regress)
    current2 = _paletted_image((4, 4), value=0)
    current2.putpixel((0, 0), 7)  # wrong color

    async def fake_stitch2(rect_arg):
        return current2

    monkeypatch.setattr(projects, "stitch_tiles", fake_stitch2)

    await proj.run_diff()

    # Should have detected regress
    assert proj.metadata.total_regress == 1
    assert proj.metadata.largest_regress_pixels == 1


async def test_run_diff_complete_status(tmp_path, monkeypatch):
    """Test complete project detection."""
    path = tmp_path / "proj_0_0_0_0.png"
    path.touch()
    rect = Rectangle.from_point_size(Point(0, 0), Size(2, 2))
    proj = projects.Project(path, rect)

    # Target and current match perfectly
    target = _paletted_image((2, 2), value=1)
    current = _paletted_image((2, 2), value=1)

    monkeypatch.setattr(PALETTE, "aopen_file", lambda path_arg: FakeAsyncImage(target))

    async def fake_stitch(rect_arg):
        return current

    monkeypatch.setattr(projects, "stitch_tiles", fake_stitch)

    await proj.run_diff()

    # Should detect as complete
    assert "Complete" in proj.metadata.last_log_message


def test_update_single_tile_metadata_updates_when_newer(tmp_path, monkeypatch, setup_config):
    """Test _update_single_tile_metadata updates when tile file is newer."""
    from pixel_hawk.geometry import Tile

    # Create a project
    path = tmp_path / "proj_0_0_0_0.png"
    path.touch()
    rect = Rectangle.from_point_size(Point(0, 0), Size(1000, 1000))
    proj = projects.Project(path, rect)

    # Create a tile file
    tile = Tile(0, 0)
    tile_path = setup_config.tiles_dir / f"tile-{tile}.png"
    tile_path.write_bytes(b"dummy")

    # Set mtime to a known value
    tile_mtime = 10000
    import os

    os.utime(tile_path, (tile_mtime, tile_mtime))

    # Set last_update to older timestamp
    proj.metadata.tile_last_update["0_0"] = 5000

    # Call the function
    proj._update_single_tile_metadata(tile)

    # Should have updated to new mtime
    assert proj.metadata.tile_last_update["0_0"] == tile_mtime
    assert ("0_0", tile_mtime) in proj.metadata.tile_updates_24h


def test_update_single_tile_metadata_skips_when_not_newer(tmp_path, monkeypatch, setup_config):
    """Test _update_single_tile_metadata skips update when tile not newer."""
    from pixel_hawk.geometry import Tile

    # Create a project
    path = tmp_path / "proj_0_0_0_0.png"
    path.touch()
    rect = Rectangle.from_point_size(Point(0, 0), Size(1000, 1000))
    proj = projects.Project(path, rect)

    # Create a tile file
    tile = Tile(0, 0)
    tile_path = setup_config.tiles_dir / f"tile-{tile}.png"
    tile_path.write_bytes(b"dummy")

    # Set mtime to a known value
    tile_mtime = 10000
    import os

    os.utime(tile_path, (tile_mtime, tile_mtime))

    # Set last_update to SAME or NEWER timestamp
    proj.metadata.tile_last_update["0_0"] = 15000
    proj.metadata.tile_updates_24h = [("0_0", 15000)]

    # Call the function
    proj._update_single_tile_metadata(tile)

    # Should NOT have updated (still the old value)
    assert proj.metadata.tile_last_update["0_0"] == 15000
    # 24h list should still have old entry only
    assert len(proj.metadata.tile_updates_24h) == 1
    assert ("0_0", 15000) in proj.metadata.tile_updates_24h


def test_update_single_tile_metadata_handles_missing_file(tmp_path, monkeypatch, setup_config):
    """Test _update_single_tile_metadata handles nonexistent tile file."""
    from pixel_hawk.geometry import Tile

    # Create a project
    path = tmp_path / "proj_0_0_0_0.png"
    path.touch()
    rect = Rectangle.from_point_size(Point(0, 0), Size(1000, 1000))
    proj = projects.Project(path, rect)

    tile = Tile(0, 0)

    # Set initial state
    proj.metadata.tile_last_update = {}
    proj.metadata.tile_updates_24h = []

    # Call the function with nonexistent tile
    proj._update_single_tile_metadata(tile)

    # Should not have added anything
    assert "0_0" not in proj.metadata.tile_last_update
    assert len(proj.metadata.tile_updates_24h) == 0


def test_has_missing_tiles_all_present(tmp_path, monkeypatch, setup_config):
    """Test _has_missing_tiles returns False when all tiles exist."""
    path = tmp_path / "proj_0_0_0_0.png"
    path.touch()
    rect = Rectangle.from_point_size(Point(0, 0), Size(1000, 1000))
    proj = projects.Project(path, rect)

    # Create all tiles for this project (just tile 0_0 since it's 1000x1000)
    for tile in rect.tiles:
        tile_file = setup_config.tiles_dir / f"tile-{tile}.png"
        tile_file.touch()

    assert proj._has_missing_tiles() is False


def test_has_missing_tiles_some_missing(tmp_path, monkeypatch, setup_config):
    """Test _has_missing_tiles returns True when some tiles are missing."""
    path = tmp_path / "proj_0_0_0_0.png"
    path.touch()
    # Project spans 2 tiles (1000x2000)
    rect = Rectangle.from_point_size(Point(0, 0), Size(1000, 2000))
    proj = projects.Project(path, rect)

    # Create only tile 0_0, not tile 0_1
    tile_file = setup_config.tiles_dir / "tile-0_0.png"
    tile_file.touch()

    assert proj._has_missing_tiles() is True


def test_has_missing_tiles_all_missing(tmp_path, monkeypatch, setup_config):
    """Test _has_missing_tiles returns True when all tiles are missing."""
    path = tmp_path / "proj_0_0_0_0.png"
    path.touch()
    rect = Rectangle.from_point_size(Point(0, 0), Size(1000, 1000))
    proj = projects.Project(path, rect)

    # Don't create any tiles
    assert proj._has_missing_tiles() is True


async def test_run_diff_sets_has_missing_tiles(tmp_path, monkeypatch, setup_config):
    """Test run_diff properly sets has_missing_tiles flag."""
    path = tmp_path / "proj_0_0_0_0.png"

    # Create a valid project image
    im = PALETTE.new((10, 10))
    im.putdata([1] * 100)
    im.save(path)

    rect = Rectangle.from_point_size(Point(0, 0), Size(10, 10))
    proj = projects.Project(path, rect)

    # Mock stitch_tiles to return a blank image
    async def fake_stitch(rect):
        return _paletted_image((10, 10), 0)

    monkeypatch.setattr(projects, "stitch_tiles", fake_stitch)

    # Run diff with no tiles in cache
    await proj.run_diff()

    # Should have detected missing tiles
    assert proj.metadata.has_missing_tiles is True

    # Now create the tile file
    tile_file = setup_config.tiles_dir / "tile-0_0.png"
    tile_file.touch()

    # Run diff again
    await proj.run_diff()

    # Should now show no missing tiles
    assert proj.metadata.has_missing_tiles is False
