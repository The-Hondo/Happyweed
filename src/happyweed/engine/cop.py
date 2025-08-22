# src/happyweed/engine/cop.py
# Minimal cop engine: holds positions, supports kill->jail behavior.
# No pathing/AI yet; this is enough to test score overlays and jail BR flip.

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple, Optional

from .collisions import RuntimeOverlay

XY = Tuple[int, int]


def jail_cells(overlay: RuntimeOverlay) -> List[XY]:
    """Return the 2x2 jail cell coordinates as a list [TL, TR, BL, BR].
    Uses overlay.jail_br_pos as the bottom-right anchor.
    """
    br = overlay.jail_br_pos
    if br is None:
        return []
    bx, by = br
    return [(bx - 1, by - 1), (bx, by - 1), (bx - 1, by), (bx, by)]


@dataclass
class Cop:
    x: int
    y: int
    in_jail: bool = False

    @property
    def pos(self) -> XY:
        return (self.x, self.y)

    def send_to_jail(self, overlay: RuntimeOverlay, slot_idx: int = 0) -> None:
        cells = jail_cells(overlay)
        if not cells:
            # No jail discovered; leave cop in place as a fallback
            self.in_jail = True
            return
        tx, ty = cells[min(max(slot_idx, 0), len(cells) - 1)]
        self.x, self.y = tx, ty
        self.in_jail = True

    def release_from_jail(self) -> None:
        self.in_jail = False
