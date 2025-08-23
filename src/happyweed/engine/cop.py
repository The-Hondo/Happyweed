# src/happyweed/engine/cop.py
# Minimal-but-structured cop engine:
# - Cop objects (position, jail state, left-spawn flag, original spawn)
# - CopManager to step all cops with a simple greedy-chase toward the player
# - Proper passability (cops can traverse jail), freeze while super active
# - On first move off spawn, the spawn tile becomes a visible leaf (80) **unconditionally**
# - Collision outcomes:
#     * If a cop reaches the player and super is active -> kill that cop (send to jail BR)
#     * If a cop reaches the player and no super -> report player_hit=True
# - Reset API: return all cops to original spawns on player death (leaves remain as-is)
# - NEW in v2.2: death reset also resets the manager's cooldown so cops don't immediately
#   step off spawn on the very next frame (which could look like they never reset).

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

from .collisions import RuntimeOverlay, is_passable_runtime, on_super_kill_player

XY = Tuple[int, int]


def jail_cells(overlay: RuntimeOverlay) -> List[XY]:
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
    left_spawn_once: bool = False
    spawn_x: int = 0
    spawn_y: int = 0

    def __post_init__(self):
        # Record original spawn immediately if not set
        if self.spawn_x == 0 and self.spawn_y == 0:
            self.spawn_x, self.spawn_y = self.x, self.y

    @property
    def pos(self) -> XY:
        return (self.x, self.y)

    def send_to_jail(self, overlay: RuntimeOverlay, slot_idx: int = 3) -> None:
        cells = jail_cells(overlay)
        if not cells:
            self.in_jail = True
            return
        slot = cells[min(max(slot_idx, 0), len(cells) - 1)]
        self.x, self.y = slot
        self.in_jail = True

    def release_from_jail(self) -> None:
        self.in_jail = False

    def reset_to_spawn(self) -> None:
        # Return to original spawn; do NOT re-hide or replant leaves.
        self.x, self.y = self.spawn_x, self.spawn_y
        self.in_jail = False
        # Intentionally keep left_spawn_once as-is (once they've left, it's true forever for this level)


@dataclass
class CopTickEvents:
    player_hit: bool = False
    points_awarded: int = 0
    kills_this_tick: int = 0


@dataclass
class CopManager:
    grid: List[List[int]]
    overlay: RuntimeOverlay
    cops: List[Cop] = field(default_factory=list)
    move_period_ticks: int = 10
    _cooldown: int = 0

    def tick(self, player_pos: XY, super_active: bool) -> CopTickEvents:
        ev = CopTickEvents()

        # Freeze during super (but resolve kills if overlapping now)
        if super_active:
            kills = [c for c in self.cops if (not c.in_jail) and c.pos == player_pos]
            if kills:
                n = len(kills)
                ev.points_awarded += on_super_kill_player(player_pos[0], player_pos[1], n_cops_on_tile=n, overlay=self.overlay)
                ev.kills_this_tick += n
                for c in kills:
                    c.send_to_jail(self.overlay, slot_idx=3)
            return ev

        # Step only on period boundaries
        if self._cooldown > 0:
            self._cooldown -= 1
            return ev
        self._cooldown = self.move_period_ticks

        px, py = player_pos

        for c in self.cops:
            if c.in_jail:
                continue

            oldx, oldy = c.x, c.y

            # Greedy toward player (deterministic); we will later replace with LST-accurate rule
            dx = 0 if c.x == px else (1 if px > c.x else -1)
            dy = 0 if c.y == py else (1 if py > c.y else -1)
            cand: List[XY] = []
            if dx != 0:
                cand.append((c.x + dx, c.y))
            if dy != 0:
                cand.append((c.x, c.y + dy))
            cand.extend([(c.x - 1, c.y), (c.x + 1, c.y), (c.x, c.y - 1), (c.x, c.y + 1)])

            moved = False
            for nx, ny in cand:
                if not self._in_bounds(nx, ny):
                    continue
                nt = self.grid[ny][nx]
                if is_passable_runtime("cop", nt, nx, ny, self.overlay):
                    c.x, c.y = nx, ny
                    moved = True
                    break

            # First leave -> force a visible leaf (80)
            if moved and not c.left_spawn_once:
                self.grid[oldy][oldx] = 80
                # Once revealed, it's never re-hidden; remove from hidden set if present
                self.overlay.cop_spawn_leaf.discard((oldx, oldy))
                c.left_spawn_once = True

            # Contact with player -> report hit when no super
            if c.pos == player_pos:
                ev.player_hit = True

        return ev

    def reset_on_player_death(self) -> None:
        """Return all cops to their original spawns. Leaves remain as-is.
        Also reset our internal cooldown so cops don't immediately step off spawn.
        """
        for c in self.cops:
            c.reset_to_spawn()
        # Hold movement for a full period after respawn so the reset is visible/stable
        self._cooldown = self.move_period_ticks
        # Do NOT touch overlay.cop_spawn_leaf

    # ---------- Helpers ----------
    def _in_bounds(self, x: int, y: int) -> bool:
        h = len(self.grid)
        w = len(self.grid[0]) if h else 0
        return 0 <= x < w and 0 <= y < h
