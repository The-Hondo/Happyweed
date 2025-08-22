# src/happyweed/engine/player.py
# Tick-based player controller with LST-style buffered turning, super inventory/use,
# and correct tile write-back semantics (leaf/super -> 180). No pygame deps.

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple, List

from .collisions import (
    RuntimeOverlay,
    is_passable_runtime,
    on_enter_player,
    FLOOR_SUBSTRATE,  # 180
)

XY = Tuple[int, int]

# 4-way directions in grid coordinates (x, y), 0-based
DIRS: Dict[str, XY] = {
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
}


@dataclass
class PlayerEvents:
    moved: bool = False
    blocked: bool = False
    leaf_collected: bool = False
    super_collected: bool = False
    exit_touched: bool = False
    level_end: bool = False   # caller sets this if exit was open
    respawned: bool = False   # reserved for cop collision wiring


class Player:
    """
    Grid-locked, tick-based player mover that matches original runtime behavior:
    - **Buffered turning**: you can press/hold a desired direction; the player will
      continue straight and turn at the **next eligible junction** without re-press.
    - **Continuous motion**: the requested direction persists; we do *not* consume it
      after a successful step.
    - **Speed control**: one tile per `MOVE_PERIOD_TICKS` (default 8). The runner can
      adjust this live to calibrate pacing.
    - **Super handling**: picking up a super adds to inventory; **SPACE** activates it.
      The sprite uses **62** while active (per latest video read), not on pickup.
    - **Write-back**: first move off spawn writes **180** underfoot; leaf/super entry
      also writes **180** (handled by `on_enter_player`).
    """

    # Tunables (to be calibrated precisely later)
    SUPER_TICKS_DEFAULT: int = 600  # ~10s at 60Hz (placeholder to match feel)

    def __init__(
        self,
        grid: List[List[int]],
        overlay: RuntimeOverlay,
        level_index: int,
        spawn_xy: XY,
    ) -> None:
        self.grid = grid
        self.overlay = overlay
        self.level = level_index
        self.x, self.y = spawn_xy
        self.spawn_xy = spawn_xy

        # Input & motion state
        self._want_dir: Optional[str] = None   # desired direction from input
        self._cur_dir: Optional[str] = None    # current movement direction (None = stopped)
        self.MOVE_PERIOD_TICKS: int = 8        # default pacing; can be changed via API
        self._move_cooldown: int = 0

        # Visual pre-move blink until first successful step
        self.pre_move_phase: bool = True
        self._pre_move_flip_counter: int = 0

        # Super state
        self.supers_held: int = 0
        self.super_ticks_remaining: int = 0

        # Spawn write-back guard
        self._spawn_writeback_pending: bool = True

    # ---------- Input API ----------

    def set_wanted_dir(self, direction: Optional[str]) -> None:
        """Set desired direction: 'up'|'down'|'left'|'right' or None. Persists until changed."""
        if direction is None:
            self._want_dir = None
            return
        if direction not in DIRS:
            raise ValueError(f"Invalid direction: {direction}")
        self._want_dir = direction

    def set_move_period(self, ticks: int) -> None:
        """Configure ticks per tile movement (>=1)."""
        self.MOVE_PERIOD_TICKS = max(1, int(ticks))

    # ---------- Super API ----------

    def activate_super(self) -> bool:
        """Activate one super from inventory. Returns True if activation succeeded."""
        if self.super_ticks_remaining > 0 or self.supers_held <= 0:
            return False
        self.supers_held -= 1
        self.super_ticks_remaining = self.SUPER_TICKS_DEFAULT
        return True

    # ---------- Tick ----------

    def tick(self, exit_open: bool) -> PlayerEvents:
        """
        Advance one tick:
        - On step boundaries (cooldown==0), attempt a buffered turn, else continue.
        - Move at most one tile per step; apply on-enter effects after moving.
        - Decrement super timer.
        """
        ev = PlayerEvents()

        # Pre-move visual blink (no logic impact)
        if self.pre_move_phase:
            self._pre_move_flip_counter = (self._pre_move_flip_counter + 1) & 0x7FFF

        # Movement only on step boundaries
        if self._move_cooldown > 0:
            self._move_cooldown -= 1
        else:
            # If we are stopped, try to start moving in the desired direction
            if self._cur_dir is None and self._want_dir is not None and self._can_move(self._want_dir):
                self._cur_dir = self._want_dir

            # At each tile boundary, attempt to turn into the desired direction if different and available
            if self._cur_dir is not None and self._want_dir and self._want_dir != self._cur_dir:
                if self._can_move(self._want_dir):
                    self._cur_dir = self._want_dir

            # Step if current direction is available
            if self._cur_dir is not None and self._can_move(self._cur_dir):
                dx, dy = DIRS[self._cur_dir]
                nx, ny = self.x + dx, self.y + dy
                next_tile = self.grid[ny][nx]

                # First move off spawn → write 180 underfoot
                if self._spawn_writeback_pending:
                    sx, sy = self.spawn_xy
                    if (self.x, self.y) == (sx, sy):
                        self.grid[sy][sx] = FLOOR_SUBSTRATE
                    self._spawn_writeback_pending = False

                # Commit the move
                self.x, self.y = nx, ny
                self.pre_move_phase = False
                ev.moved = True

                # Enter-effects (mutates grid/overlay)
                enter = on_enter_player(next_tile, nx, ny, self.level, self.overlay, self.grid)
                ev.leaf_collected = enter["leaf_collected"]
                ev.super_collected = enter["super_collected"]
                ev.exit_touched = enter["exit_touched"]

                if ev.super_collected:
                    # Pickup adds to inventory; activation is manual via SPACE
                    self.supers_held += 1

                if ev.exit_touched and exit_open:
                    ev.level_end = True

                # Reset cooldown for next step
                self._move_cooldown = self.MOVE_PERIOD_TICKS
            else:
                # Could not move this tick
                ev.blocked = True
                # If blocked in current dir, stop; desired remains queued for future
                if self._cur_dir is not None and not self._can_move(self._cur_dir):
                    self._cur_dir = None

        # Super timer countdown
        if self.super_ticks_remaining > 0:
            self.super_ticks_remaining -= 1

        return ev

    # ---------- Helpers ----------

    def _can_move(self, direction: str) -> bool:
        dx, dy = DIRS[direction]
        nx, ny = self.x + dx, self.y + dy
        if not self._in_bounds(nx, ny):
            return False
        next_tile = self.grid[ny][nx]
        return is_passable_runtime("player", next_tile, nx, ny, self.overlay)

    def _in_bounds(self, x: int, y: int) -> bool:
        h = len(self.grid)
        w = len(self.grid[0]) if h else 0
        return 0 <= x < w and 0 <= y < h

    # ---------- Rendering helpers (no pygame here) ----------

    def sprite_tile(self) -> int:
        """Return the player sprite tile id for this tick.
        - Pre-move: blink 60/61
        - Super active: 62
        - Normal: 60
        """
        if self.super_ticks_remaining > 0:
            return 62
        if self.pre_move_phase:
            # Toggle every 8 ticks (tune later against video)
            return 60 if ((self._pre_move_flip_counter >> 3) & 1) == 0 else 61
        return 60

    # ---------- External state queries ----------

    @property
    def pos(self) -> XY:
        return (self.x, self.y)

    @property
    def super_active(self) -> bool:
        return self.super_ticks_remaining > 0

    @property
    def cur_dir(self) -> Optional[str]:
        return self._cur_dir

    def force_respawn(self, xy: Optional[XY] = None) -> None:
        """Respawn at original spawn or at provided coordinate. Caller handles lives/state."""
        if xy is None:
            xy = self.spawn_xy
        self.x, self.y = xy
        self.pre_move_phase = True
        self._pre_move_flip_counter = 0
        self._spawn_writeback_pending = True
        self._cur_dir = None
        # Super is not reset here; caller decides.
