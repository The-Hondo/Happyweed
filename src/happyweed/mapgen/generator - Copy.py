from dataclasses import dataclass
from typing import List, Tuple
from ..rng import PMRandom, seed_from_E, E_from_set_level
from ..tiles import LEAF, PLAYER, COP, EXIT, wall_for_level, superdrug_for_level, is_open
from ..grid import Grid, VISIBLE_W, VISIBLE_H

BASE_SEED = 0x0B6E755A  # Observed pre-stream origin (see docs/lst_notes.md)

@dataclass
class LevelSpec:
    level_set: int
    level: int

def _place_outer_rim(g: Grid, wall: int) -> None:
    for x in range(VISIBLE_W):
        g.set(x, 0, wall)
        g.set(x, VISIBLE_H-1, wall)
    for y in range(VISIBLE_H):
        g.set(0, y, wall)
        g.set(VISIBLE_W-1, y, wall)

def generate_grid(level_set: int, level: int) -> List[List[int]]:
    E = E_from_set_level(level_set, level)
    seed = seed_from_E(BASE_SEED, E)
    rng = PMRandom(seed)

    wall = wall_for_level(level)
    g = Grid.empty(wall_tile=wall)
    _place_outer_rim(g, wall)

    carve(g, rng)
    place_items(g, rng, level)
    return g.as_visible_matrix()

# --- Carving (placeholder to be refined with exact lst turn codes) ---
DIRS = [(1,0),(0,1),(-1,0),(0,-1)]  # R,D,L,U
def carve(g: Grid, rng: PMRandom) -> None:
    # Start within 2..17 x 2..10
    x = (rng.bounded(14) + 1) + 1  # 2..17
    y = (rng.bounded(8) + 1) + 1   # 2..10
    dir_idx = 0  # Right
    steps = 0
    MAX_STEPS = 135
    while steps < MAX_STEPS:
        t = rng.bounded(16) - 1  # 0..15
        if t in (0,4,8,12):
            dir_idx = (dir_idx + 3) & 3     # left
        elif t in (2,6,10,14):
            dir_idx = (dir_idx + 1) & 3     # right
        dx, dy = DIRS[dir_idx]
        nx, ny = x + dx, y + dy
        if 1 < nx < VISIBLE_W-1 and 1 < ny < VISIBLE_H-1:
            g.set(nx, ny, LEAF)             # unconditional overwrite
            x, y = nx, ny
            steps += 1
        else:
            dir_idx = (dir_idx + 1) & 3     # rotate when facing rim

def _find_candidates_wall_adjacent_open(g: Grid) -> List[Tuple[int,int]]:
    cands = []
    for y in range(1, VISIBLE_H-1):
        for x in range(1, VISIBLE_W-1):
            v = g.get(x,y)
            if v >= 200:  # wall-ish (255 included)
                for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
                    if is_open(g.get(x+dx,y+dy)):
                        cands.append((x,y)); break
    return cands

def _rand_from_list(rng: PMRandom, lst: List[Tuple[int,int]]) -> Tuple[int,int]:
    idx = rng.bounded(len(lst)) - 1
    return lst[idx]

def place_items(g: Grid, rng: PMRandom, level: int) -> None:
    # superdrugs: 3,2,1 by level bands
    n_super = 3 if level <= 4 else (2 if level <= 9 else 1)
    super_tile = superdrug_for_level(level)
    for _ in range(n_super):
        cands = _find_candidates_wall_adjacent_open(g)
        if not cands: break
        x,y = _rand_from_list(rng, cands)
        g.set(x,y, super_tile)

    # cops x3
    for _ in range(3):
        cands = _find_candidates_wall_adjacent_open(g)
        if not cands: break
        x,y = _rand_from_list(rng, cands)
        g.set(x,y, COP)

    # exit
    cands = _find_candidates_wall_adjacent_open(g)
    if cands:
        x,y = _rand_from_list(rng, cands)
        g.set(x,y, EXIT)

    # player
    cands = _find_candidates_wall_adjacent_open(g)
    if cands:
        x,y = _rand_from_list(rng, cands)
        g.set(x,y, PLAYER)

    # jail 2x2 (simplified placeholder; will be replaced with exact lst logic)
    from ..tiles import JAIL_TL,JAIL_TR,JAIL_BL,JAIL_BR
    for y in range(2, VISIBLE_H-2):
        for x in range(2, VISIBLE_W-2):
            if all(g.get(x+dx, y+dy) >= 200 for dx in (0,1) for dy in (0,1)):
                # neighbor open from BR corner?
                bx, by = x+1, y+1
                for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
                    if is_open(g.get(bx+dx, by+dy)):
                        g.set(x,y,JAIL_TL); g.set(x+1,y,JAIL_TR)
                        g.set(x,y+1,JAIL_BL); g.set(x+1,y+1,JAIL_BR)
                        return
