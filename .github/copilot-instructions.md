**Project Overview**

wwpppp is a small watcher for WPlace paint projects. It polls WPlace tile images, stitches cached tiles, and diffs them against project image files a user places in their platform pictures folder. The package entry point is exposed as the console script `wwpppp` (see `pyproject.toml`).

**Quick facts**
- **Requires:** Python >= 3.14 (see `pyproject.toml`)
- **Console script:** `wwpppp = "wwpppp.main:main"`
- **Main package:** `src/wwpppp`
- **Key dependencies:** `loguru`, `pillow`, `platformdirs`, `requests`
- **Linting:** `ruff` configured with `line-length = 120`

**Quickstart (developer)**
See the `uv` documentation: https://pypi.org/project/uv/

- Use `uv` to manage Python and project dependencies. Example:

```powershell
uv sync
```

- Run the watcher locally with the console script or module (via your `uv` environment):

```powershell
uv run wwpppp
```

**Where data lives**
- The package uses `platformdirs.PlatformDirs("wwpppp")` and exposes `DIRS` from `src/wwpppp/__init__.py`.
- User pictures path: `DIRS.user_pictures_path / "wplace"` — drop project PNGs here.
- Cache path: `DIRS.user_cache_path` — tile cache (`tile-<tx>_<ty>.png`) and `projects.db` SQLite cache.

**How it works (high level)**
- The application runs in a unified 2-minute polling loop that checks both tiles and project files.
- `has_tile_changed()` (in `ingest.py`) requests tiles from the WPlace tile backend and updates a cached paletted PNG if there are changes.
- `Project` (in `projects.py`) discovers project PNGs placed under the `wplace` pictures folder. Filenames must include coordinates (regex used in code) and must use the project's palette.
- `PALETTE` (in `palette.py`) enforces and converts images to the project palette (first color treated as transparent).
- `Main` (in `main.py`) runs the polling loop: `check_tiles()` polls all tiles for changes, `check_projects()` scans for new/modified/deleted project files. On tile changes it diffs updated tiles with project images and logs progress.

**File/Module map (where to look)**
- `src/wwpppp/__init__.py` — `DIRS` (platform dirs)
- `src/wwpppp/main.py` — application entry, unified polling loop, project load/forget logic
- `src/wwpppp/geometry.py` — `Tile`, `Point`, `Size`, `Rectangle` helpers (tile math)
- `src/wwpppp/ingest.py` — `has_tile_changed()`, tile download and stitching helper
- `src/wwpppp/palette.py` — palette enforcement + helper `PALETTE`
- `src/wwpppp/projects.py` — `Project` model, caching, diffs

- The project is in early stages: public APIs and internals may change. Prefer simplicity, clarity, and small, focused edits.
- Follow existing idioms: use `NamedTuple`/`dataclass`-like shapes, type hints, and explicit resource management (`with` for PIL Images).
- Preserve logging via `loguru` rather than replacing with ad-hoc prints.
- Image handling:
  - Use `PALETTE.ensure(image)` for conversion; avoid manually mutating palettes.
  - Always close PIL `Image` objects; prefer `with Image.open(...) as im:` or the helper patterns already present.
- SQLite cache: use `CachedProjectMetadata` abstraction rather than writing ad-hoc SQL elsewhere.
- Error handling: prefer non-fatal logging (warnings/debug) and avoid raising unexpected exceptions in the polling loop.

**Developer workflow & checks**
- Linting: run `ruff` (project defines `line-length = 120`).
- Formatting: no explicit formatter in repo; follow current style and ruff suggestions.
- Tests: unit tests live under `tests/`. We use `pytest` with `pytest-cov` for coverage.
  - Coverage is configured in `pyproject.toml` under `[tool.pytest.ini_options]`.
  - The project enforces a coverage threshold for all modules.
  - Focus tests on `geometry`, `palette.lookup`, and `projects` diff logic.
  - Run tests: `uv run pytest`

**Running and debugging**
- To debug tile fetching behavior, call `has_tile_changed()` directly with a `Tile` object in an interactive script and observe `DIRS.user_cache_path` for generated `tile-*.png` files.
- To debug project parsing, drop a correctly named PNG into `DIRS.user_pictures_path / 'wplace'` and watch the log output from `Main`.

**Notes for Copilot (how to suggest changes)**
- Suggest minimal, testable code changes and include brief rationale in the PR description.
- When adding features, propose where to add unit tests (suggest `tests/test_geometry.py`, `tests/test_palette.py`).
- If modifying image handling, show the expected lifecycle (open -> ensure palette -> close) and indicate why conversions are safe.
- Prefer explicit, type-annotated functions and small helper functions over large refactors.

**Packaging & distribution**
- `pyproject.toml` contains project metadata and the console script entry point.
- Use `uv sync` for dependency management and installation.

**Safety & Resource constraints**
- Network I/O is used in `ingest.has_tile_changed`. Keep short timeouts and avoid unbounded parallel downloads.
- Polling: The main loop sleeps for 120 seconds (2 minutes) between cycles. Ensure operations complete within reasonable time.

**Where to look for further context**
- `pyproject.toml` for packaging/deps and `ruff` config
- `README.md` for user-facing documentation and external resources/links
- `tests/` for unit tests and test patterns
- [local-instructions.md](local-instructions.md) for instructions regarding user conversation and the development environment
