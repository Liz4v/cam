import io

import requests
from loguru import logger
from PIL import Image

from . import DIRS
from .geometry import Rectangle, Size, Tile
from .palette import PALETTE


def has_tile_changed(tile: Tile) -> bool:
    """Downloads the indicated tile from the server and updates the cache. Returns whether it changed."""
    url = f"https://backend.wplace.live/files/s0/tiles/{tile.x}/{tile.y}.png"
    response = requests.get(url, timeout=5)
    if response.status_code != 200:
        logger.debug(f"Tile {tile}: HTTP {response.status_code}")
        return False
    data = response.content
    try:
        img = Image.open(io.BytesIO(data))
    except Exception as e:
        logger.debug(f"Tile {tile}: image decode failed: {e}")
        return False
    with PALETTE.ensure(img) as paletted:
        cache_path = DIRS.user_cache_path / f"tile-{tile}.png"
        if cache_path.exists():
            with Image.open(cache_path) as cached:
                if bytes(cached.tobytes()) == bytes(paletted.tobytes()):
                    logger.info(f"Tile {tile}: No change detected.")
                    return False  # no change
        logger.info(f"Tile {tile}: Change detected, updating cache...")
        paletted.save(cache_path)
    return True


def stitch_tiles(rect: Rectangle) -> Image.Image:
    """Stitches tiles from cache together, exactly covering the given rectangle."""
    image = PALETTE.new(rect.size)
    for tile in rect.tiles:
        cache_path = DIRS.user_cache_path / f"tile-{tile}.png"
        if not cache_path.exists():
            logger.warning(f"{tile}: Tile missing from cache, leaving transparent")
            continue
        with Image.open(cache_path) as tile_image:
            offset = tile.to_point() - rect.point
            image.paste(tile_image, Rectangle.from_point_size(offset, Size(1000, 1000)))
    return image
