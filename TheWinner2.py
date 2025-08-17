#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple
import argparse

# Park–Miller constants (Classic Mac _Random core)
A = 16807
M = 0x7FFFFFFF
# Modular inverse of A modulo M (so we can step the RNG **backward** exactly)
INV_A = 1407677000  # because (A * INV_A) % M == 1

# --- Level seed derivation from (set, level) ---
# We use the invariant K = set_idx + 8*level_idx and a reference seed/state.
# Reference: Set 41, Level 1 -> seed_ref = 0x010760F5 at the FIRST _Random call.


def seed_from_set_level(set_idx: int, level_idx: int) -> int:
    """Derive the **pre-call** Park–Miller state for (set, level).

    Closed form from data & listing behavior:
    Let K = set + 8*(level-1).
    Then the FIRST _Random return at level start is:
        s1 = (A*K + C) mod M
    where A = 16807 (Park–Miller multiplier), M = 2^31-1, and C = 0x0FCDD36.
    (Equivalently: s1(K+8) = s1(K) + 8*A, i.e., constant additive step per level.)

    The generator uses pre-call seed0, which is prev(s1).
    """
    K = set_idx + 8*(level_idx - 1)
    s1 = (A * K + 0x0FCDD36) % M
    return pm_prev(s1)


def pm_next(seed: int) -> int:
    return (seed * A) % M

def pm_prev(seed: int) -> int:
    return (seed * INV_A) % M

@dataclass
class PMRandomMac:
    """Classic Mac _Random-compatible wrapper (advance-then-return).

    Semantics: each call advances the 31-bit Park–Miller state once, then
    returns the new state (like Toolbox _Random). This class expects to be
    initialized with the **pre-call** seed (the state *before* the first _Random).
    """
    seed: int  # 31-bit pre-call state

    def random32_and_advance(self) -> int:
        # ADVANCE first, then return (matches _Random)
        self.seed = pm_next(self.seed & 0x7FFFFFFF)
        return self.seed

    def randN_bounded(self, N: int) -> int:
        v32 = self.random32_and_advance()
        w = v32 & 0xFFFF
        if w & 0x8000:  # signed 16
            w = -(((~w) & 0xFFFF) + 1)
        return (abs(w) % N) + 1

# Tiles
def TILE_WALL(level_idx: int) -> int:
    # Levels 21–25 use 255 for walls; otherwise 200+level
    return 255 if 21 <= level_idx <= 25 else 200 + level_idx

TILE_PLAYER  = 60
TILE_COP     = 66
TILE_LEAF    = 80

def TILE_SUPER(level_idx: int) -> int:
    # Levels 15–25 use 255 for super drugs; otherwise 80+level
    return 255 if 15 <= level_idx <= 25 else 80 + level_idx

TILE_EXIT    = 241
TILE_JAIL_TL = 250
TILE_JAIL_TR = 251
TILE_JAIL_BL = 252
TILE_JAIL_BR = 253

# Bounds (1-based, interior)
X_MIN, X_MAX = 2, 18
Y_MIN, Y_MAX = 2, 11

def level_digits(n: int) -> Tuple[int,int,int]:
    return (n // 100) % 10, (n // 10) % 10, n % 10

def in_walk_bounds(x: int, y: int) -> bool:
    return X_MIN <= x <= X_MAX and Y_MIN <= y <= Y_MAX

def is_open_tile(tile: int) -> bool:
    # matches sub_74C6 with arg2=0: open is strictly 10..199
    return 10 <= tile <= 199

# Jail-specific openness: walkable floor only (exclude player & cops)
def is_open_for_jail(tile: int) -> bool:
    return (10 <= tile <= 199) and (tile not in (TILE_PLAYER, TILE_COP))

# ---- exact carve direction state machine (matches listing) ----
# dir_state d3: 0=Left, 1=Right, 2=Down, 3=Up

def apply_turn_code(tcode: int, dir_state: int, dx: int, dy: int):
    if tcode == 0:
        if dir_state != 1:
            return (-1, 0, 0)
    elif tcode == 1:
        if dir_state != 0:
            return ( 1, 0, 1)
    elif tcode == 2:
        if dir_state != 3:
            return ( 0, 1, 2)
    elif tcode == 3:
        if dir_state != 2:
            return ( 0,-1, 3)
    return (dx, dy, dir_state)

# ---- placement helpers (mirror sub_89BC / sub_8AAC) ----

def place_random_item(grid, rng: PMRandomMac, level_idx: int, tile_id: int):
    wall = TILE_WALL(level_idx)
    while True:
        x = rng.randN_bounded(17) + 1   # 2..18
        y = rng.randN_bounded(10) + 1   # 2..11
        if grid[y-1][x-1] != wall:
            continue
        # neighbor must include at least one "open" (10..199)
        for nx, ny in ((x-1,y), (x+1,y), (x,y-1), (x,y+1)):
            t = grid[ny-1][nx-1]
            if is_open_tile(t):
                grid[y-1][x-1] = tile_id
                return (x, y)


def place_jail(grid, rng: PMRandomMac, level_idx: int):
    wall = TILE_WALL(level_idx)
    while True:
        # Listing uses same sampling span; the 2x2 check below filters out edges.
        cx = rng.randN_bounded(17) + 1   # candidate center-right/bottom coords
        cy = rng.randN_bounded(10) + 1
        # top-left of the 2x2 will be (cx-1, cy-1)
        tlx, tly = cx-1, cy-1
        if not (X_MIN <= tlx <= X_MAX-1 and Y_MIN <= tly <= Y_MAX-1):
            continue
        # require all 2x2 to be interior wall (200+level)
        if not (grid[tly-1][tlx-1] == wall and
                grid[tly-1][tlx]   == wall and
                grid[tly][tlx-1]   == wall and
                grid[tly][tlx]     == wall):
            continue
        # adjacency check from the BR corner (cx, cy) to open
        for nx, ny in ((cx-1,cy), (cx+1,cy), (cx,cy-1), (cx,cy+1)):
            t = grid[ny-1][nx-1]
            if is_open_for_jail(t):
                grid[tly-1][tlx-1] = TILE_JAIL_TL
                grid[tly-1][tlx]   = TILE_JAIL_TR
                grid[tly][tlx-1]   = TILE_JAIL_BL
                grid[tly][tlx]     = TILE_JAIL_BR
                return (tlx, tly)
        # else keep searching


def generate_level(
    set_idx: int,
    level_idx: int,
    seed: int,
    mode: str = "steps",               # "steps" or "tick"
    steps_cap: int = 135,
    tick_provider: Optional[Callable[[int], int]] = None
) -> List[List[int]]:
    # NOTE: seed is the 31-bit Park–Miller state people usually log at
    # the *first* _Random call (e.g., 0x0B6E755A). We backstep once inside
    # PMRandomMac so the first low-16 observed is the game’s 0x60F5.
    rng = PMRandomMac(seed & 0x7FFFFFFF)
    wall = TILE_WALL(level_idx)

    # init grid
    W, H = 20, 12
    # Fill the entire 20x12 grid with the level's wall tile; the carve will open paths.
    grid = [[wall for _ in range(W)] for __ in range(H)]

    # HUD digits (top-left)
    h,t,o = level_digits(level_idx)
    grid[0][0], grid[0][1], grid[0][2] = h,t,o

    # carve start
    x = rng.randN_bounded(14) + 3
    y = rng.randN_bounded(8)  + 3
    dx, dy = 1, 0
    dir_state = 0  # (Left) in the listing, even though dx=+1

    steps = 0
    start_tick = None
    if mode == "tick":
        if tick_provider is None:
            raise ValueError("tick mode needs tick_provider")
        start_tick = tick_provider(0)

    while True:
        if mode == "steps":
            if steps >= min(steps_cap, 135):
                break
        else:
            def s16(v):
                v &= 0xFFFF
                return v-0x10000 if v & 0x8000 else v
            cur = tick_provider(steps)
            if s16(cur) > s16(start_tick) + 3 or steps >= 135:
                break

        tcode = rng.randN_bounded(16) - 1
        dx, dy, dir_state = apply_turn_code(tcode, dir_state, dx, dy)
        nx, ny = x + dx, y + dy
        if in_walk_bounds(nx, ny):
            grid[ny-1][nx-1] = TILE_LEAF  # unconditional write
            x, y = nx, ny
            steps += 1

    # placers (order from caller/sub_8736 & generator/sub_879A)
    super_count = max(1, 3 - (level_idx // 5))
    for _ in range(super_count):
        place_random_item(grid, rng, level_idx, TILE_SUPER(level_idx))
    for _ in range(3):
        place_random_item(grid, rng, level_idx, TILE_COP)
    place_random_item(grid, rng, level_idx, TILE_EXIT)
    place_random_item(grid, rng, level_idx, TILE_PLAYER)
    place_jail(grid, rng, level_idx)
    return grid


def print_grid(grid: List[List[int]]) -> None:
    for row in grid:
        print(" ".join(str(v) for v in row))


def main():
    ap = argparse.ArgumentParser(description="Happyweed! level generator (exact THINK C logic).")
    ap.add_argument("--set",   type=int, required=True)
    ap.add_argument("--level", type=int, required=True)
    ap.add_argument("--seed",  type=lambda x: int(x, 0), required=False, default=None,
                    help=(
                        "Optional override: 31-bit Park–Miller PRE-call state (before first _Random). "
                        "If omitted, we derive it from set/level using the closed-form seed."
                    ))
    ap.add_argument("--steps", type=int, default=135)
    args = ap.parse_args()

    seed = args.seed if args.seed is not None else seed_from_set_level(args.set, args.level)
    grid = generate_level(args.set, args.level, seed, steps_cap=args.steps)
    print_grid(grid)


if __name__ == "__main__":
    main()
