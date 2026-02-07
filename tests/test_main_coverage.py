"""Additional tests to improve main.py coverage."""

import time
from pathlib import Path
from types import SimpleNamespace

from wwpppp import main as main_mod
from wwpppp import projects


def test_check_projects_handles_modified_files(tmp_path, monkeypatch):
    """Test that check_projects detects modified files via mtime."""
    wplace_dir = tmp_path / "wplace"
    wplace_dir.mkdir()

    monkeypatch.setattr(
        main_mod, "DIRS", SimpleNamespace(user_pictures_path=tmp_path, user_cache_path=tmp_path / "cache")
    )

    monkeypatch.setattr(projects.Project, "iter", classmethod(lambda cls: []))
    m = main_mod.Main()

    proj_path = wplace_dir / "proj_0_0_1_1.png"
    proj_path.touch()

    class DummyProj:
        def __init__(self, path):
            self.path = path
            self.rect = SimpleNamespace(tiles=frozenset())
            self.mtime = path.stat().st_mtime

        def run_diff(self):
            pass

        def forget(self):
            pass

    monkeypatch.setattr(projects.Project, "try_open", classmethod(lambda cls, p: DummyProj(p)))

    # Load the project first
    m.check_projects()
    assert proj_path in m.projects

    # Modify the file (change mtime)
    import time

    time.sleep(0.01)
    proj_path.touch()

    # Track if load_project is called again
    load_called = {"count": 0}
    original_load = m.load_project

    def track_load(p):
        load_called["count"] += 1
        original_load(p)

    m.load_project = track_load

    # check_projects should detect the modification
    m.check_projects()
    assert load_called["count"] >= 1


def test_file_modified_returns_true_on_oserror(tmp_path, monkeypatch):
    """Test that _file_modified returns True when stat() raises OSError."""
    monkeypatch.setattr(projects.Project, "iter", classmethod(lambda cls: []))
    m = main_mod.Main()

    proj_path = tmp_path / "nonexistent.png"

    class DummyProj:
        def __init__(self):
            self.path = proj_path
            self.mtime = 12345.0

    m.projects[proj_path] = DummyProj()

    # _file_modified should return True because stat() will fail on nonexistent file
    assert m._file_modified(proj_path) is True


def test_load_project_handles_stat_oserror(tmp_path, monkeypatch):
    """Test that load_project handles OSError when getting mtime."""
    wplace_dir = tmp_path / "wplace"
    wplace_dir.mkdir()

    monkeypatch.setattr(projects.Project, "iter", classmethod(lambda cls: []))
    m = main_mod.Main()

    proj_path = wplace_dir / "proj_0_0_1_1.png"

    class DummyProj:
        def __init__(self, path):
            self.path = path
            self.rect = SimpleNamespace(tiles=frozenset())

        def run_diff(self):
            pass

        def forget(self):
            pass

    loaded_proj = None

    def capture_proj(cls, p):
        nonlocal loaded_proj
        loaded_proj = DummyProj(p)
        return loaded_proj

    monkeypatch.setattr(projects.Project, "try_open", classmethod(capture_proj))

    # Mock Path.stat to raise OSError for this specific path
    from pathlib import Path

    original_stat = Path.stat

    def mock_stat(self, *args, **kwargs):
        if self == proj_path:
            raise OSError("Mock error")
        return original_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", mock_stat)

    # load_project should handle the OSError and set mtime to None
    m.load_project(proj_path)
    assert proj_path in m.projects
    assert loaded_proj.mtime is None


def test_main_function_calls_run_forever(monkeypatch):
    """Test that the main() function creates Main and calls run_forever."""
    called = {"init": False, "run": False}

    # Monkeypatch Project.iter to avoid real initialization
    monkeypatch.setattr(projects.Project, "iter", classmethod(lambda cls: []))

    original_main_class = main_mod.Main

    class FakeMain(original_main_class):
        def __init__(self):
            called["init"] = True
            super().__init__()

        def run_forever(self):
            called["run"] = True
            # Don't actually run forever, just mark as called
            return

    monkeypatch.setattr(main_mod, "Main", FakeMain)

    # Call main() - should create Main and call run_forever
    main_mod.main()

    assert called["init"] is True
    assert called["run"] is True


def test_check_projects_skips_deleted_files_in_current_loop(tmp_path, monkeypatch):
    """Test that check_projects doesn't try to load files that are in deleted set."""
    wplace_dir = tmp_path / "wplace"
    wplace_dir.mkdir()

    monkeypatch.setattr(
        main_mod, "DIRS", SimpleNamespace(user_pictures_path=tmp_path, user_cache_path=tmp_path / "cache")
    )

    # Start with one project already loaded
    proj_path = wplace_dir / "proj_0_0_1_1.png"

    class DummyProj:
        def __init__(self, path):
            self.path = path
            self.rect = SimpleNamespace(tiles=frozenset())
            self.mtime = None

        def run_diff(self):
            pass

        def forget(self):
            pass

    existing_proj = DummyProj(proj_path)

    monkeypatch.setattr(projects.Project, "iter", classmethod(lambda cls: [existing_proj]))
    m = main_mod.Main()

    # Create a different file on disk
    other_path = wplace_dir / "other_0_0_1_1.png"
    other_path.touch()

    monkeypatch.setattr(projects.Project, "try_open", classmethod(lambda cls, p: DummyProj(p)))

    # Track calls
    forgot_called = []
    loaded_called = []

    original_forget = m.forget_project
    original_load = m.load_project

    def track_forget(p):
        forgot_called.append(p)
        original_forget(p)

    def track_load(p):
        loaded_called.append(p)
        original_load(p)

    m.forget_project = track_forget
    m.load_project = track_load

    # check_projects should:
    # 1. Forget proj_path (not on disk)
    # 2. Load other_path (new file on disk)
    # 3. NOT try to load proj_path even though it's in the loop
    m.check_projects()

    assert proj_path in forgot_called
    assert other_path in loaded_called
    # proj_path should not be in loaded_called (this tests the "if path in deleted: continue")
    assert proj_path not in loaded_called


def test_run_forever_sleeps_and_loops(monkeypatch):
    """Test that run_forever sleeps between cycles and can be interrupted."""
    monkeypatch.setattr(projects.Project, "iter", classmethod(lambda cls: []))
    m = main_mod.Main()

    sleep_calls = []
    cycle_count = {"count": 0}

    def mock_sleep(seconds):
        sleep_calls.append(seconds)
        # Interrupt after first sleep
        raise KeyboardInterrupt

    monkeypatch.setattr(time, "sleep", mock_sleep)

    def mock_check_tiles():
        cycle_count["count"] += 1

    def mock_check_projects():
        pass

    m.check_tiles = mock_check_tiles
    m.check_projects = mock_check_projects

    # run_forever should loop, call check methods, sleep, then be interrupted
    m.run_forever()

    # Should have called check_tiles once and tried to sleep
    assert cycle_count["count"] >= 1
    assert len(sleep_calls) == 1
    assert sleep_calls[0] == 127  # ~2 minutes with drift


def test_file_modified_returns_true_when_no_project(tmp_path, monkeypatch):
    """Test that _file_modified returns True when project doesn't exist."""
    monkeypatch.setattr(projects.Project, "iter", classmethod(lambda cls: []))
    m = main_mod.Main()

    proj_path = tmp_path / "notloaded.png"

    # _file_modified should return True because the project isn't loaded
    assert m._file_modified(proj_path) is True
