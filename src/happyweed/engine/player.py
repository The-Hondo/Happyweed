# src/happyweed/engine/player.py
"""
Tick-based player mover with exact 'open tile' checks and buffered turns.

Key invariants (from the original LST & project doctrine):
- "Open" tiles are strictly 10..199 (inclusive).
- Movement is grid-based, one tile per tick update() call.
- A desired turn can be buffered; it executes as soon as the target tile is open.
- If neither the buffered turn nor forward direction is open, the player stays put.

This module does NOT impose scoring/leaf-consumption—callers can pass an
'on_enter' callback to mutate the grid and update score/lives etc.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Optional, Tuple, List

# Directions: 0=Left, 1=Right, 2=Down, 3=Up (matches carve/generator convention)
DIR_LEFT, DIR_RIGHT, DIR_DOWN, DIR_UP = 0, 1, 2, 3
_DIR_TO_DELTA = {
    DIR_LEFT:  (-1, 0),
    DIR_RIGHT: ( 1, 0),
    DIR_DOWN:  ( 0, 1),
    DIR_UP:    ( 0,-1),
}

def is_open_tile(tile_id: int) -> bool:
    """Strict open range used across the project."""
    return 10 <= tile_id <= 199

@dataclass
class PlayerState:
    # 0-based grid coordinates (20x12 visible field)
    x: int
    y: int
    # Current direction (one of DIR_*), or None if stationary.
    dir: Optional[int] = None
    # Buffered desired turn to apply ASAP (None if none).
    desired: Optional[int] = None

    def as_tuple(self) -> Tuple[int,int]:
        return (self.x, self.y)

OnEnterFn = Callable[[int, int, int], Optional[int]]
# Signature: on_enter(x, y, tile_id) -> new_tile_id or None (to leave as-is)

def find_player_start(grid: List[List[int]], player_tile_id: int) -> Tuple[int,int]:
    """Scan the 20x12 grid for the player tile; return (x,y) or (-1,-1) if missing."""
    for y in range(12):
        row = grid[y]
        for x in range(20):
            if row[x] == player_tile_id:
                return (x, y)
    return (-1, -1)

def _can_step(grid: List[List[int]], x: int, y: int) -> bool:
    # Bounds check then open check
    if not (0 <= x < 20 and 0 <= y < 12):
        return False
    return is_open_tile(grid[y][x])

def _apply_on_enter(grid: List[List[int]], x: int, y: int, on_enter: Optional[OnEnterFn]) -> None:
    if on_enter is None:
        return
    new_tile = on_enter(x, y, grid[y][x])
    if new_tile is not None:
        grid[y][x] = new_tile

def set_desired(state: PlayerState, direction: Optional[int]) -> None:
    """Update the desired (buffered) direction."""
    state.desired = direction

def set_direction_immediate(state: PlayerState, direction: Optional[int]) -> None:
    """Force current direction now (usually only in tests or when spawning)."""
    state.dir = direction

def update_player(
    grid: List[List[int]],
    state: PlayerState,
    *,
    on_enter: Optional[OnEnterFn] = None
) -> None:
    """
    Advance the player by one tick (one tile step at most):
      1) If desired turn is set and target tile is open, apply the turn and move.
      2) Else if forward tile is open, continue forward.
      3) Else stay in place (blocked).
    Calls 'on_enter' after a successful move, allowing the caller to mutate the tile.
    """
    # 1) Try to take the buffered turn if possible
    if state.desired is not None:
        dx, dy = _DIR_TO_DELTA[state.desired]
        nx, ny = state.x + dx, state.y + dy
        if _can_step(grid, nx, ny):
            state.x, state.y = nx, ny
            state.dir = state.desired
            _apply_on_enter(grid, state.x, state.y, on_enter)
            return
        # If desired blocked, we don't clear it: keep buffering it

    # 2) Try to continue forward
    if state.dir is not None:
        dx, dy = _DIR_TO_DELTA[state.dir]
        nx, ny = state.x + dx, state.y + dy
        if _can_step(grid, nx, ny):
            state.x, state.y = nx, ny
            _apply_on_enter(grid, state.x, state.y, on_enter)
            return

    # 3) Blocked; do nothing
    return
