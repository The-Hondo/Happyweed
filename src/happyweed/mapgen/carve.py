# src/happyweed/mapgen/carve.py
# Exact leaf-carve algorithm (no placements), mirroring the original listing.
# Coordinates are 1-based inside the interior playfield (2..18, 2..11).

from typing import List, Tuple, Optional, Callable
from ..rng import PMRandom
from ..tiles import LEAF, wall_for_level

# Bounds (1-based interior)
X_MIN, X_MAX = 2, 18
Y_MIN, Y_MAX = 2, 11

def in_walk_bounds(x: int, y: int) -> bool:
    return X_MIN <= x <= X_MAX and Y_MIN <= y <= Y_MAX

# dir_state d3: 0=Left, 1=Right, 2=Down, 3=Up
def apply_turn_code(tcode: int, dir_state: int, dx: int, dy: int):
    # Turn codes are sampled 0..15. Only the low two bits matter; the
    # original accepts 0..3 and treats others as “straight/no change”.
    # Prevent immediate reversals per LST logic:
    if tcode == 0:
        # Turn to Left  (dx=-1,dy=0) unless we’re currently Right
        if dir_state != 1:
            return (-1, 0, 0)
    elif tcode == 1:
        # Turn to Right (dx=+1,dy=0) unless we’re currently Left
        if dir_state != 0:
            return ( 1, 0, 1)
    elif tcode == 2:
        # Turn to Down  (dx=0,dy=+1) unless we’re currently Up
        if dir_state != 3:
            return ( 0, 1, 2)
    elif tcode == 3:
        # Turn to Up    (dx=0,dy=-1) unless we’re currently Down
        if dir_state != 2:
            return ( 0,-1, 3)
    return (dx, dy, dir_state)

def empty_wall_grid(level_idx: int) -> List[List[int]]:
    """Return a fresh 20×12 grid filled with the correct wall tile for level."""
    wall = wall_for_level(level_idx)
    return [[wall for _ in range(20)] for _ in range(12)]

def carve_leaf_grid(
    level_idx: int,
    rng: PMRandom,
    mode: str = "steps",                 # "steps" (cap only) or "tick" (tick-based timeout)
    steps_cap: int = 135,
    tick_provider: Optional[Callable[[int], int]] = None,
) -> List[List[int]]:
    """
    Produce a 20×12 grid whose interior leaf trail matches the original game.
    Outer rim is walls, and interior starts as walls; we write LEAF (80) as we walk.
    """
    grid = empty_wall_grid(level_idx)

    # Start position: x ∈ [4..17], y ∈ [4..11] (1-based), per LST (+3 offset).
    # PMRandom.bounded returns 1..N inclusive.
    x = rng.bounded(14) + 3   # 4..17
    y = rng.bounded(8)  + 3   # 4..11

    # Initial heading: dx=+1,dy=0, but dir_state is stored as “Left” (0) in the listing.
    dx, dy = 1, 0
    dir_state = 0  # (Left) per disassembly, even though dx=+1

    steps = 0
    start_tick = None
    if mode == "tick":
        if tick_provider is None:
            raise ValueError("tick mode requires tick_provider")
        # The original uses signed 16-bit TickCount math; our tests use steps mode,
        # but we keep the API shape for later parity.
        def s16(v: int) -> int:
            v &= 0xFFFF
            return v - 0x10000 if (v & 0x8000) else v
        start_tick = tick_provider(0) & 0xFFFF

    while True:
        # Termination
        if mode == "steps":
            if steps >= steps_cap:
                break
        else:
            # tick mode: end if (cur > start+3) or steps >= 135, using signed 16-bit compare
            cur = (tick_provider(steps) if tick_provider else 0) & 0xFFFF
            if (((cur & 0xFFFF) - (start_tick & 0xFFFF)) & 0x8000) == 0 and ((cur - start_tick) & 0xFFFF) > 3:
                break
            if steps >= 135:
                break

        # Turn selection — sample 0..15, only 0..3 change heading (others = straight)
        tcode = rng.bounded(16) - 1  # 0..15
        dx, dy, dir_state = apply_turn_code(tcode, dir_state, dx, dy)

        nx, ny = x + dx, y + dy
        if in_walk_bounds(nx, ny):
            # Unconditional write of leaf tile (80)
            grid[ny-1][nx-1] = LEAF
            x, y = nx, ny
            steps += 1
        # Else: ignore and try another turn next iteration (no implicit rotate)

    return grid
