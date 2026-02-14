from pixel_hawk.palette import PALETTE


def test_lookup_transparent():
    # alpha 0 should map to palette index 0
    report = {}
    assert PALETTE.lookup(report, (1, 2, 3, 0)) == 0
    assert report == {}


def test_lookup_unknown_color_tracked():
    # use an unlikely RGB value that's not in palette
    report = {}
    result = PALETTE.lookup(report, (250, 251, 252, 255))
    assert result == 0
    rgb = (250 << 16) | (251 << 8) | 252
    assert report == {rgb: 1}


def test_new_creates_paletted_image():
    im = PALETTE.new((2, 2))
    assert im.mode == "P"
    # transparency should be set to palette index 0
    assert im.info.get("transparency") == 0


def test_ensure_converts_rgba_and_lookup_valid_color():
    from PIL import Image

    # pick a known palette color from internal index list
    rgb_int = PALETTE._idx[0]
    r = (rgb_int >> 16) & 0xFF
    g = (rgb_int >> 8) & 0xFF
    b = rgb_int & 0xFF

    # create an RGBA image with that color and ensure conversion
    im = Image.new("RGBA", (2, 2), (r, g, b, 255))
    pal = PALETTE.ensure(im)
    assert pal.mode == "P"
    # ensure lookup for the color returns a non-zero palette index
    report = {}
    assert PALETTE.lookup(report, (r, g, b, 255)) != 0
    assert report == {}


def test_open_file_with_existing_paletted_file(tmp_path):
    path = tmp_path / "pal.png"
    im = PALETTE.new((2, 2))
    im.putdata([0, 1, 2, 3])
    im.save(path)

    opened = PALETTE.open_file(path)
    assert opened.mode == "P"


def test_ensure_rgba_conversion_for_rgb_image():
    from PIL import Image

    from pixel_hawk.palette import _ensure_rgba

    rgb_im = Image.new("RGB", (1, 1), (1, 2, 3))
    rgba = _ensure_rgba(rgb_im)
    assert rgba.mode == "RGBA"


def test_lookup_wrong_teal_mapping():
    # The palette maps 0x10AE82 to the same index as 0x10AEA6
    teal = 0x10AE82
    r = (teal >> 16) & 0xFF
    g = (teal >> 8) & 0xFF
    b = teal & 0xFF
    report = {}
    idx = PALETTE.lookup(report, (r, g, b, 255))
    assert isinstance(idx, int)
    assert report == {}
