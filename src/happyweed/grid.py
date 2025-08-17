from dataclasses import dataclass
from typing import List

WIDTH_BACKING = 30
VISIBLE_W, VISIBLE_H = 20, 12

@dataclass
class Grid:
    buf: List[int]
    stride: int = WIDTH_BACKING

    @classmethod
    def empty(cls, wall_tile: int) -> "Grid":
        # Backing buffer defaults to wall; visible rim will be set explicitly.
        buf = [wall_tile] * (cls.stride * VISIBLE_H)
        return cls(buf=buf)

    def idx(self, x: int, y: int) -> int:
        return y * self.stride + x

    def get(self, x: int, y: int) -> int:
        return self.buf[self.idx(x, y)]

    def set(self, x: int, y: int, v: int) -> None:
        self.buf[self.idx(x, y)] = v

    def as_visible_matrix(self) -> List[List[int]]:
        out = []
        for y in range(VISIBLE_H):
            row = [self.get(x, y) for x in range(VISIBLE_W)]
            out.append(row)
        return out
