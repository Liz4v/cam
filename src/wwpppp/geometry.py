import functools
import typing


class Point(typing.NamedTuple):
    x: int = 0
    y: int = 0

    @classmethod
    def from4(cls, tx: int, ty: int, px: int, py: int) -> "Point":
        return cls(tx * 1000 + px, ty * 1000 + py)

    def to4(self) -> tuple[int, int, int, int]:
        tx, px = divmod(self.x, 1000)
        ty, py = divmod(self.y, 1000)
        return tx, ty, px, py

    def __str__(self) -> str:
        return "_".join(map(str, self.to4()))

    def __sub__(self, other: "Point") -> "Point":
        return Point(self.x - other.x, self.y - other.y)


class Size(typing.NamedTuple):
    w: int = 0
    h: int = 0

    def __str__(self) -> str:
        return f"{self.w}x{self.h}"


class Rectangle(typing.NamedTuple):
    point: Point = Point()
    size: Size = Size()

    def __str__(self):
        return f"{self.point}-{self.size}"

    def __contains__(self, other: "Rectangle") -> bool:
        return (
            self.point.x <= other.point.x
            and other.point.x + other.size.w <= self.point.x + self.size.w
            and self.point.y <= other.point.y
            and other.point.y + other.size.h <= self.point.y + self.size.h
        )

    def __sub__(self, other: Point) -> "Rectangle":
        return Rectangle(self.point - other, self.size)

    @property
    @functools.cache
    def box(self) -> tuple[int, int, int, int]:
        return (self.point.x, self.point.y, self.point.x + self.size.w, self.point.y + self.size.h)
