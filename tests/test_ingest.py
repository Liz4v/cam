import io
from pathlib import Path
from types import SimpleNamespace

from wwpppp import DIRS
from wwpppp.geometry import Point, Rectangle, Size, Tile
from wwpppp.ingest import has_tile_changed, stitch_tiles
from wwpppp.palette import PALETTE


def _paletted_png_bytes(size=(1, 1), data=(0,)):
    im = PALETTE.new(size)
    im.putdata(list(data))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def test_has_tile_changed_http_error(monkeypatch, tmp_path):
    monkeypatch.setattr("wwpppp.ingest.DIRS", SimpleNamespace(user_cache_path=tmp_path, user_pictures_path=tmp_path))

    class Resp:
        status_code = 404
        content = b""

    monkeypatch.setattr("wwpppp.ingest.requests.get", lambda *a, **k: Resp())
    assert not has_tile_changed(Tile(0, 0))


def test_has_tile_changed_bad_image(monkeypatch, tmp_path):
    monkeypatch.setattr("wwpppp.ingest.DIRS", SimpleNamespace(user_cache_path=tmp_path, user_pictures_path=tmp_path))

    class Resp:
        status_code = 200
        content = b"not an image"

    monkeypatch.setattr("wwpppp.ingest.requests.get", lambda *a, **k: Resp())
    assert not has_tile_changed(Tile(0, 0))


def test_has_tile_changed_no_change_and_change(monkeypatch, tmp_path):
    monkeypatch.setattr("wwpppp.ingest.DIRS", SimpleNamespace(user_cache_path=tmp_path, user_pictures_path=tmp_path))
    png = _paletted_png_bytes()

    class Resp:
        status_code = 200
        content = png

    monkeypatch.setattr("wwpppp.ingest.requests.get", lambda *a, **k: Resp())

    # create existing identical cache -> no change
    cache_path = tmp_path / "tile-0_0.png"
    cache_path.write_bytes(png)
    assert not has_tile_changed(Tile(0, 0))

    # remove cache -> change detected and file created
    cache_path.unlink()
    assert has_tile_changed(Tile(0, 0))
    assert cache_path.exists()


def test_stitch_tiles_pastes_cached_tiles(monkeypatch, tmp_path):
    monkeypatch.setattr("wwpppp.ingest.DIRS", SimpleNamespace(user_cache_path=tmp_path, user_pictures_path=tmp_path))
    # create two tile cache files at (0,0) and (1,0)
    png_a = _paletted_png_bytes((1000, 1000), [1] * (1000 * 1000))
    png_b = _paletted_png_bytes((1000, 1000), [2] * (1000 * 1000))
    (tmp_path / "tile-0_0.png").write_bytes(png_a)
    (tmp_path / "tile-1_0.png").write_bytes(png_b)

    rect = Rectangle.from_point_size(Point(0, 0), Size(2000, 1000))
    stitched = stitch_tiles(rect)
    assert stitched.size == rect.size
    # check that some pixels are non-zero indicating pasted content
    data = stitched.get_flattened_data()
    assert any(p for p in data)
