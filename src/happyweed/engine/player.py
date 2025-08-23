# src/happyweed/engine/player.py
# Engine-only Player: buffered turns, tile-by-tile stepping, pause-aware, super stock/use,
# spawn restoration to 180, and runtime enter-effects via collisions.

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .collisions import (
    FLOOR_SUBSTRATE,
    RuntimeOverlay,
    is_passable_runtime,
    on_enter_player,
)

XY = Tuple[int, int]


_DIRS = {
    "left": (-1, 0),
    "right": (1, 0),
    "up": (0, -1),
    "down": (0, 1),
}


@dataclass
class Player:
    grid: List[List[int]]
    overlay: RuntimeOverlay
    level_index: int
    spawn_xy: XY

    # dynamic fields (filled in __post_init__)
    x: int = 0
    y: int = 0
    cur_dir: Optional[str] = None
    wanted_dir: Optional[str] = None

    # timing/movement
    MOVE_PERIOD_TICKS: int = 8
    _cooldown: int = 0

    # pause & visuals
    pre_move_phase: bool = True  # GameState controls this; true during prestart/death pause
    _idle_frame: int = 60        # 60↔61 while paused

    # super drug
    super_active: bool = False
    super_ticks: int = 0
    super_stock: int = 0         # collected but not yet used
    SUPER_DURATION_TICKS: int = 600  # placeholder; to be calibrated from LST

    # misc
    _first_move_done: bool = False
    reached_exit: bool = False

    def __post_init__(self) -> None:
        self.x, self.y = self.spawn_xy
        # Player sprite may be baked on the grid; keep it visually but treat substrate as 180 on leave
        self._cooldown = self.MOVE_PERIOD_TICKS

    # ------------- API expected by runner/state -------------
    @property
    def pos(self) -> XY:
        return (self.x, self.y)

    def set_move_period(self, ticks: int) -> None:
        self.MOVE_PERIOD_TICKS = max(1, int(ticks))
        # Nudge cooldown into range so speed changes feel immediate but not jarring
        self._cooldown = min(self._cooldown, self.MOVE_PERIOD_TICKS)

    def set_wanted_dir(self, direction: Optional[str]) -> None:
        if direction in _DIRS or direction is None:
            self.wanted_dir = direction

    def toggle_idle_frame(self) -> None:
        # Only used during pre-move pauses by GameState
        self._idle_frame = 61 if self._idle_frame == 60 else 60

    def sprite_tile(self) -> int:
        if self.super_active:
            return 62  # per video; confirm in LST if 62 vs 63
        if self.pre_move_phase:
            return self._idle_frame
        return 60

    def activate_super(self) -> None:
        # Manual use of a collected super; no effect if already active
        if self.super_stock > 0 and not self.super_active:
            self.super_stock -= 1
            self.super_active = True
            self.super_ticks = self.SUPER_DURATION_TICKS

    def force_respawn(self) -> None:
        # Used by GameState on death
        self.x, self.y = self.spawn_xy
        self.cur_dir = None
        self.wanted_dir = None
        self._cooldown = self.MOVE_PERIOD_TICKS
        self.pre_move_phase = True
        self.reached_exit = False
        # Do NOT change super state here (original keeps super off after death; stock preserved)
        self.super_active = False
        self.super_ticks = 0

    # ------------- Core tick -------------
    def tick(self, *, exit_open: bool) -> Dict[str, bool]:
        """Advance one engine tick. Returns event flags from on-enter.
        Movement happens only when not in pre_move_phase and cooldown hits zero.
        """
        # Super countdown
        if self.super_active:
            if self.super_ticks > 0:
                self.super_ticks -= 1
            if self.super_ticks == 0:
                self.super_active = False

        # Paused: no movement, no on-enter
        if self.pre_move_phase:
            return {"moved": False}

        # Movement cadence
        if self._cooldown > 0:
            self._cooldown -= 1
            return {"moved": False}
        self._cooldown = self.MOVE_PERIOD_TICKS

        moved = self._try_step(exit_open=exit_open)
        return {"moved": moved}

    # ------------- Helpers -------------
    def _try_step(self, *, exit_open: bool) -> bool:
        # Try to adopt wanted_dir if it is now legal
        if self.wanted_dir and self._can_move(self.wanted_dir):
            self.cur_dir = self.wanted_dir

        # If no current direction, try to start with wanted
        if not self.cur_dir and self.wanted_dir and self._can_move(self.wanted_dir):
            self.cur_dir = self.wanted_dir

        # If still no direction (or blocked), try to keep current; else we stop
        if not self.cur_dir or not self._can_move(self.cur_dir):
            # As a last resort, try wanted again (corner case when current is blocked)
            if self.wanted_dir and self._can_move(self.wanted_dir):
                self.cur_dir = self.wanted_dir
            else:
                return False

        dx, dy = _DIRS[self.cur_dir]
        nx, ny = self.x + dx, self.y + dy

        # Check passability at target
        if not self._in_bounds(nx, ny):
            return False
        tile = self.grid[ny][nx]
        if not is_passable_runtime("player", tile, nx, ny, self.overlay):
            return False

        # --- Perform the step ---
        ox, oy = self.x, self.y
        self.x, self.y = nx, ny

        # Restore the tile we stepped off from if it's the baked spawn (or any player sprite)
        if not self._first_move_done:
            # First movement of the life → clear original spawn footprint to 180
            self.grid[oy][ox] = FLOOR_SUBSTRATE
            self._first_move_done = True

        # Enter effects: leaves/supers/exit touch
        ev = on_enter_player(tile, nx, ny, self.level_index, self.overlay, self.grid)
        if ev.get("super_collected"):
            self.super_stock += 1
        if ev.get("exit_touched") and exit_open:
            self.reached_exit = True
        return True

    def _can_move(self, direction: str) -> bool:
        if direction not in _DIRS:
            return False
        dx, dy = _DIRS[direction]
        nx, ny = self.x + dx, self.y + dy
        if not self._in_bounds(nx, ny):
            return False
        tile = self.grid[ny][nx]
        return is_passable_runtime("player", tile, nx, ny, self.overlay)

    def _in_bounds(self, x: int, y: int) -> bool:
        h = len(self.grid)
        w = len(self.grid[0]) if h else 0
        return 0 <= x < w and 0 <= y < h
