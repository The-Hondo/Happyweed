# src/happyweed/mapgen/jail.py
from typing import List, Tuple
from ..rng import PMRandom
from ..tiles import (
    JAIL_TL, JAIL_TR, JAIL_BL, JAIL_BR,
    PLAYER, COP, wall_for_level
)

def is_open_for_jail(tile: int) -> bool:
    # Walkable “floor” only (10..199) EXCLUDING player/cops
    return (10 <= tile <= 199) and (tile not in (PLAYER, COP))

def place_jail(
    grid: List[List[int]],
    rng: PMRandom,
    level_idx: int
) -> Tuple[int,int]:
    """
    Matches listing:
    - Sample (cx ∈ 2..18, cy ∈ 2..11).
    - Treat (cx-1,cy-1) as the TL of the 2×2 candidate.
    - Require that TL ∈ 2..17 and TL.y ∈ 2..10 (so the 2×2 is fully interior).
    - Require all 4 cells of the 2×2 to be the current level’s WALL.
    - Require that the BR corner (cx,cy) has at least one open-for-jail neighbor.
    - Write 250,251,252,253 as TL,TR,BL,BR and return (cx-1, cy-1) TL in 1-based terms.
    """
    wall = wall_for_level(level_idx)
    while True:
        cx = rng.bounded(17) + 1   # 2..18
        cy = rng.bounded(10) + 1   # 2..11
        tlx, tly = cx - 1, cy - 1

        # TL must be interior so that the 2×2 is interior: 2..17, 2..10
        if not (2 <= tlx <= 17 and 2 <= tly <= 10):
            continue

        # Check 2×2 are all walls of this level
        if not all(grid[(tly-1)+dy][(tlx-1)+dx] == wall for dy in (0,1) for dx in (0,1)):
            continue

        # Neighbor-open test from BR corner (cx,cy)
        brx, bry = cx, cy
        if not any(
            is_open_for_jail(grid[(bry-1)+dy][(brx-1)+dx])
            for dx,dy in ((1,0),(-1,0),(0,1),(0,-1))
        ):
            continue

        # Place jail tiles
        grid[tly-1][tlx-1] = JAIL_TL
        grid[tly-1][tlx   ] = JAIL_TR
        grid[tly  ][tlx-1] = JAIL_BL
        grid[tly  ][tlx   ] = JAIL_BR
        return (tlx, tly)
