import functools
import itertools
import pathlib

from PIL import Image


@functools.cache
class Palette:
    def __init__(self):
        path = pathlib.Path(__file__).with_suffix(".txt")
        raw = bytearray()
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("#"):
                    raw.extend(int(line[1:7], 16).to_bytes(3, "big"))

        self.raw = bytes(raw)
        self.dict = {}
        for i, triplet in enumerate(itertools.batched(self.raw, 3)):
            self.dict[tuple(triplet)] = i
        del self.dict[tuple(self.raw[0:3])]  # remove placeholder color

        self.image = Image.new("P", (1, 1))
        self.image.putpalette(self.raw)

    def ensure_palette(self, image: Image.Image) -> Image.Image:
        if image.mode == "P" and image.getpalette() == list(self.raw):
            return image
        print("Converting image to palette...")
        rgba = image.convert("RGBA")
        image.close()
        data = bytearray()
        for *triplet, a in rgba.getdata():
            data.append(0 if a == 0 else self.dict.get(tuple(triplet), 0))
        rgba.close()
        paletted = Image.new("P", image.size)
        paletted.putpalette(self.raw)
        paletted.putdata(bytes(data))
        paletted.info["transparency"] = 0
        return paletted
