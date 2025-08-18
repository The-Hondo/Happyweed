# src/happyweed/mapgen/placement.py
from typing import Tuple, List
from ..rng import PMRandom
from ..tiles import (
    PLAYER, COP, EXIT, LEAF,
    wall_for_level, superdrug_for_level
)

# Open classification per LST: strictly 10..199
def is_open_tile(tile: int) -> bool:
    return 10 <= tile <= 199

def _has_open_neighbor(grid: List[List[int]], x: int, y: int) -> bool:
    # x,y are 1-based interior coords (2..18, 2..11) when called
    # grid is [row][col] 0-based
    for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
        t = grid[(y-1)+dy][(x-1)+dx]
        if is_open_tile(t):
            return True
    return False

def place_random_item(
    grid: List[List[int]],
    rng: PMRandom,
    level_idx: int,
    tile_id: int
) -> Tuple[int,int]:
    """
    Matches the listing’s random wall-with-open-neighbor sampling:
    - Pick (x ∈ 2..18, y ∈ 2..11) via two bounded RNG draws.
    - Require the target cell to be the current level’s wall tile.
    - Require at least one 4-neighbor to be “open” (10..199).
    - Write the tile and return (x,y) when found.
    """
    wall = wall_for_level(level_idx)
    while True:
        x = rng.bounded(17) + 1   # 2..18
        y = rng.bounded(10) + 1   # 2..11
        if grid[y-1][x-1] != wall:
            continue
        if not _has_open_neighbor(grid, x, y):
            continue
        grid[y-1][x-1] = tile_id
        return (x, y)

def apply_all_placements(
    grid: List[List[int]],
    rng: PMRandom,
    level_idx: int
) -> None:
    """
    Order (from sub_8736 / sub_879A):
      1) superdrug(s) — 3,2,1 by level bands; tile is 80+L (L≤14) else 255
      2) cops ×3
      3) exit
      4) player
      5) jail (in jail.py)
    """
    # superdrugs: 1..3 depending on level band
    super_count = max(1, 3 - (level_idx // 5))  # 1 at 10+, 2 at 5..9, 3 at 1..4
    s_tile = superdrug_for_level(level_idx)
    for _ in range(super_count):
        place_random_item(grid, rng, level_idx, s_tile)

    # cops ×3
    for _ in range(3):
        place_random_item(grid, rng, level_idx, COP)

    # exit, then player
    place_random_item(grid, rng, level_idx, EXIT)
    place_random_item(grid, rng, level_idx, PLAYER)
