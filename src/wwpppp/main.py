from .palette import Palette
from .projects import get_project_paths


def main():
    palette = Palette()
    print("Palette loaded:", palette)

    for proj in get_project_paths():
        image = palette.open_image(proj.path)
        image.show()
        print("Project found:", proj.path, "at coords", proj.coords)


if __name__ == "__main__":
    main()
