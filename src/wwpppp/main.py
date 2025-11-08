from PIL import Image

from .palette import Palette
from .projects import get_project_paths


def main():
    palette = Palette()
    print("Palette loaded:", palette)

    for proj in get_project_paths():
        image = Image.open(proj.path)
        paletted_image = palette.ensure_palette(image)
        paletted_image.show()
        print("Project found:", proj.path, "at coords", proj.coords)


if __name__ == "__main__":
    main()
