import pytest

from pixel_hawk.geometry import GeoPoint, Point, Rectangle, Size, Tile


def test_point_from4_and_to4():
    p = Point.from4(1, 2, 3, 4)
    assert p.x == 1003 and p.y == 2004
    assert p.to4() == (1, 2, 3, 4)


def test_point_str_and_to_point():
    t = Tile(2, 3)
    assert str(t) == "2_3"
    pt = t.to_point(10, 20)
    assert pt == Point(2010, 3020)
    assert str(Point.from4(2, 3, 10, 20)) == "2_3_10_20"


def test_point_from4_assertions():
    with pytest.raises(AssertionError):
        Point.from4(-1, 0, 0, 0)
    with pytest.raises(AssertionError):
        Point.from4(0, 0, 1000, 0)


def test_point_subtraction():
    a = Point(1500, 2500)
    b = Point(500, 1000)
    c = a - b
    assert c == Point(1000, 1500)


def test_size_and_rectangle_tiles():
    size = Size(1500, 2000)
    assert bool(size)
    rect = Rectangle.from_point_size(Point(500, 500), size)
    # tiles should cover tiles for tx in {0,1} and ty in {0,1,2}
    tiles = rect.tiles
    assert Tile(0, 0) in tiles
    assert Tile(1, 2) in tiles
    assert len(tiles) == 6


def test_rectangle_properties_and_ops():
    p = Point(0, 0)
    s = Size(100, 200)
    r = Rectangle.from_point_size(p, s)
    assert r.point == p
    assert r.size == s
    assert "100x200" in str(r)
    assert r
    # subtraction by point
    r2 = r - Point(10, 20)
    assert r2.left == -10 and r2.top == -20
    # empty rectangle
    r_empty = Rectangle(0, 0, 0, 0)
    assert not r_empty


GEO_EXAMPLES = [
    # Known locations
    (Point(1024000, 1024000), GeoPoint(0.0, 0.0)),
    # Eyeballed points
    (Point(573355, 747984), GeoPoint(43.582364791630496, -79.21485384697264)),
    (Point(733393, 1023987), GeoPoint(0.0021975969721476077, -51.08317415947268)),
    (Point(2006342, 1299716), GeoPoint(-43.54427966409443, 172.67739224677734)),
    (Point(558527, 2047999), GeoPoint(-85.05112116917313, -81.82133822197264)),
]


@pytest.mark.parametrize("pixel, geo", GEO_EXAMPLES)
def test_point_to_geo(pixel: Point, geo: GeoPoint):
    result = pixel.to_geo()
    assert abs(result.latitude - geo.latitude) < 0.001
    assert abs(result.longitude - geo.longitude) < 0.001


@pytest.mark.parametrize("pixel, geo", GEO_EXAMPLES)
def test_geopoint_to_pixel(pixel: Point, geo: GeoPoint):
    result = geo.to_pixel()
    assert abs(result.x - pixel.x) <= 1
    assert abs(result.y - pixel.y) <= 1


def test_geo_round_trip():
    """Point -> GeoPoint -> Point should round-trip within 1 pixel."""
    for pt, _ in GEO_EXAMPLES:
        recovered = pt.to_geo().to_pixel()
        assert abs(recovered.x - pt.x) <= 1
        assert abs(recovered.y - pt.y) <= 1


def test_geo_round_trip_reverse():
    """GeoPoint -> Point -> GeoPoint should round-trip within tight tolerance."""
    for _, geo in GEO_EXAMPLES:
        recovered = geo.to_pixel().to_geo()
        assert abs(recovered.latitude - geo.latitude) < 0.0001
        assert abs(recovered.longitude - geo.longitude) < 0.0001
