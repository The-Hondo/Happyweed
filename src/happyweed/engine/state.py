# src/happyweed/engine/state.py
# GameState orchestrator with prestart/death pauses + TimingModel integration.

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Set, Tuple

from ..mapgen.generator import generate_grid
from .player import Player
from .cop import Cop, CopManager, jail_cells
from .collisions import (
    FLOOR_SUBSTRATE,
    RuntimeOverlay,
    build_runtime_overlay,
    tick_overlay,
    exit_is_open,
    on_super_kill_player,
)
from .timing import TimingModel, timing_for

XY = Tuple[int, int]


def _in_bounds(grid: List[List[int]], x: int, y: int) -> bool:
    h = len(grid)
    w = len(grid[0]) if h else 0
    return 0 <= x < w and 0 <= y < h


def _find_player_spawn_by_tile(grid: List[List[int]]) -> Optional[XY]:
    for y, row in enumerate(grid):
        for x, t in enumerate(row):
            if t in (60, 61, 62, 63):
                return (x, y)
    return None


def _infer_spawn(grid: List[List[int]]) -> XY:
    cx, cy = 10, 6
    if _in_bounds(grid, cx, cy) and 10 <= grid[cy][cx] <= 199:
        return (cx, cy)
    for r in range(1, 20):
        for dx in range(-r, r + 1):
            for dy in (-r, r):
                x, y = cx + dx, cy + dy
                if _in_bounds(grid, x, y) and 10 <= grid[y][x] <= 199:
                    return (x, y)
        for dy in range(-r + 1, r):
            for dx in (-r, r):
                x, y = cx + dx, cy + dy
                if _in_bounds(grid, x, y) and 10 <= grid[y][x] <= 199:
                    return (x, y)
    return (0, 0)


def _super_tile_id_for_level(level: int) -> int:
    return 80 + level if level <= 14 else 255


def infer_supers(grid: List[List[int]], level: int) -> Set[XY]:
    positions: Set[XY] = set()
    if level <= 14:
        target = _super_tile_id_for_level(level)
        for y, row in enumerate(grid):
            for x, t in enumerate(row):
                if t == target:
                    positions.add((x, y))
    elif 15 <= level <= 20:
        for y, row in enumerate(grid):
            for x, t in enumerate(row):
                if t == 255:
                    positions.add((x, y))
    return positions


def _find_cops(grid: List[List[int]]) -> List[Cop]:
    cops: List[Cop] = []
    for y, row in enumerate(grid):
        for x, t in enumerate(row):
            if t in (65, 66, 67):
                cops.append(Cop(x, y))
    return cops


def _count_leaves(grid: List[List[int]], overlay: RuntimeOverlay) -> int:
    visible = sum(1 for row in grid for t in row if t == 80)
    hidden = len(overlay.cop_spawn_leaf)
    return visible + hidden


@dataclass
class TickOut:
    exit_open: bool
    points_gained: int


class GameState:
    def __init__(
        self,
        level_set: int,
        level: int,
        *,
        player_step_ticks: Optional[int] = None,
        cop_step_ticks: Optional[int] = None,
        menu_speed_index: int = 2,
        spawn_override: Optional[XY] = None,
        super_overrides: Optional[Set[XY]] = None,
    ) -> None:
        # Map
        self.grid = generate_grid(level_set, level)
        self.level = level

        # Timing model (scalable)
        self.timing = timing_for(menu_speed_index)
        if player_step_ticks is not None:
            self.timing.player_period = player_step_ticks
        if cop_step_ticks is not None:
            self.timing.cop_period = cop_step_ticks

        # Overlay
        self.overlay = build_runtime_overlay(self.grid, super_positions=infer_supers(self.grid, level))
        if super_overrides:
            self.overlay.super_positions.update(super_overrides)

        # Cops
        self.cops = _find_cops(self.grid)
        self.overlay.cop_spawn_leaf = {c.pos for c in self.cops}
        self.copman = CopManager(grid=self.grid, overlay=self.overlay, cops=self.cops, move_period_ticks=max(1, self.timing.cop_period))

        # Player
        spawn_xy = spawn_override or _find_player_spawn_by_tile(self.grid) or _infer_spawn(self.grid)
        self.player = Player(grid=self.grid, overlay=self.overlay, level_index=level, spawn_xy=spawn_xy)
        self.player.set_move_period(self.timing.player_period)

        # Exit FSM flags
        self._close_armed = True
        if self.overlay.exit_pos is not None:
            self.overlay.exit_frame = 249
            self.overlay.exit_dir = 0
            self.overlay.exit_timer = 1

        # Pauses
        self.paused_ticks = self.timing.prestart_ticks
        self._blink_accum = 0

        # Score
        self.total_points = 0

    # ---- Lifecycle helpers ----
    def _force_exit_closed_hold(self) -> None:
        if self.overlay.exit_pos is not None:
            self.overlay.exit_frame = 241
            self.overlay.exit_dir = 0
            self.overlay.exit_timer = 1

    def _begin_pause(self, ticks: int) -> None:
        self.paused_ticks = max(0, ticks)
        # Hold cops one full period after pause to mirror spawn-visibility pause
        try:
            self.copman._cooldown = self.copman.move_period_ticks
        except Exception:
            pass
        # Player stays in pre-move phase so input buffers but no steps are taken
        self.player.pre_move_phase = True

    def handle_player_death(self) -> None:
        self.player.force_respawn()
        self._force_exit_closed_hold()
        try:
            self.copman.reset_on_player_death()
        except Exception:
            for c in self.cops:
                if hasattr(c, "spawn_x"):
                    c.x, c.y = c.spawn_x, c.spawn_y
                    c.in_jail = False
        self._begin_pause(self.timing.death_pause_ticks)

    # ---- Tick orchestration ----
    def tick(self) -> TickOut:
        # Paused: only blink sprite + tick overlays for score/jail; no movement
        if self.paused_ticks > 0:
            self.paused_ticks -= 1
            # Blink cadence for player 60↔61 while paused
            self._blink_accum += 1
            if self._blink_accum >= self.timing.sprite_blink_period:
                self._blink_accum = 0
                if hasattr(self.player, "toggle_idle_frame"):
                    self.player.toggle_idle_frame()
            # Keep overlays alive (score timers, etc.), but exit stays static
            tick_overlay(self.overlay, leaves_remaining=_count_leaves(self.grid, self.overlay), super_active=self.player.super_active, grid=self.grid)
            return TickOut(exit_open=exit_is_open(self.overlay), points_gained=0)

        # Unpause transitions: enable player stepping
        self.player.pre_move_phase = False

        # 1) Cops step first; may kill player
        cev = self.copman.tick(player_pos=self.player.pos, super_active=self.player.super_active)
        self.total_points += cev.points_awarded
        if cev.player_hit and not self.player.super_active:
            self.handle_player_death()
            return TickOut(exit_open=exit_is_open(self.overlay), points_gained=cev.points_awarded)

        # 2) Player step
        exit_open_before = exit_is_open(self.overlay)
        _pev = self.player.tick(exit_open=exit_open_before)

        # 3) One-time closing after first successful move
        if self._close_armed and not self.player.pre_move_phase:
            if self.overlay.exit_pos is not None:
                self.overlay.exit_dir = -1
                if self.overlay.exit_timer <= 0:
                    self.overlay.exit_timer = 1
            self._close_armed = False

        # 4) Overlap collisions after player move
        if not self.player.super_active:
            if any((not c.in_jail) and c.pos == self.player.pos for c in self.cops):
                self.handle_player_death()
                return TickOut(exit_open=exit_is_open(self.overlay), points_gained=0)
        else:
            overlapping = [c for c in self.cops if (not c.in_jail) and c.pos == self.player.pos]
            if overlapping:
                n = len(overlapping)
                self.total_points += on_super_kill_player(self.player.pos[0], self.player.pos[1], n_cops_on_tile=n, overlay=self.overlay)
                cells = jail_cells(self.overlay)
                br = cells[-1] if cells else None
                for c in overlapping:
                    c.send_to_jail(self.overlay, slot_idx=3)
                    if br:
                        c.x, c.y = br

        # 5) Timers: exit cadence, score FX lifetime, jail BR revert
        tick_overlay(self.overlay, leaves_remaining=_count_leaves(self.grid, self.overlay), super_active=self.player.super_active, grid=self.grid)

        return TickOut(exit_open=exit_is_open(self.overlay), points_gained=0)
