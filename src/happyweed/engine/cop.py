# src/happyweed/engine/cop.py
# Minimal-but-structured cop engine:
# - Cop objects (position, jail state, left-spawn flag)
# - CopManager to step all cops with a simple greedy-chase toward the player
# - Proper passability (cops can traverse jail), freeze while super active
# - On first move off spawn, the spawn tile becomes a visible leaf (80) **unconditionally**
# - Collision outcomes:
#     * If a cop reaches the player and super is active -> kill that cop (send to jail BR)
#     * If a cop reaches the player and no super -> report player_hit=True

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

from .collisions import RuntimeOverlay, is_passable_runtime, on_super_kill_player

XY = Tuple[int, int]


def jail_cells(overlay: RuntimeOverlay) -> List[XY]:
    """Return the 2x2 jail cell coordinates as a list [TL, TR, BL, BR],
    using overlay.jail_br_pos as the bottom-right anchor. Missing -> [].
    """
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

    @property
    def pos(self) -> XY:
        return (self.x, self.y)

    def send_to_jail(self, overlay: RuntimeOverlay, slot_idx: int = 3) -> None:
        cells = jail_cells(overlay)
        if not cells:
            # No jail discovered; keep position but mark jailed
            self.in_jail = True
            return
        # Default to BR slot (index 3) unless a specific slot is provided
        slot = cells[min(max(slot_idx, 0), len(cells) - 1)]
        self.x, self.y = slot
        self.in_jail = True

    def release_from_jail(self) -> None:
        self.in_jail = False


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
    move_period_ticks: int = 10  # slower than player by default; tune later
    _cooldown: int = 0

    def tick(self, player_pos: XY, super_active: bool) -> CopTickEvents:
        ev = CopTickEvents()

        # Freeze during super
        if super_active:
            # Collision check: if any cop shares player's tile, treat as kill(s)
            kills = [c for c in self.cops if (not c.in_jail) and c.pos == player_pos]
            if kills:
                n = len(kills)
                ev.points_awarded += on_super_kill_player(player_pos[0], player_pos[1], n_cops_on_tile=n, overlay=self.overlay)
                ev.kills_this_tick += n
                # Send all to jail BR and mark jailed
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
                continue  # stay in jail until external release policy (not implemented yet)

            # First move off spawn -> reveal a visible leaf (80) at the cell they leave
            oldx, oldy = c.x, c.y

            # Decide next step with a simple greedy toward player (deterministic)
            dx = 0 if c.x == px else (1 if px > c.x else -1)
            dy = 0 if c.y == py else (1 if py > c.y else -1)

            # Preference order: primary axis first, then secondary, then try orthogonals
            cand: List[XY] = []
            if dx != 0:
                cand.append((c.x + dx, c.y))
            if dy != 0:
                cand.append((c.x, c.y + dy))
            # Fallback orthogonals (keep deterministic order L,R,U,D around current)
            cand.extend([(c.x - 1, c.y), (c.x + 1, c.y), (c.x, c.y - 1), (c.x, c.y + 1)])

            moved = False
            for nx, ny in cand:
                if not self._in_bounds(nx, ny):
                    continue
                nt = self.grid[ny][nx]
                if is_passable_runtime("cop", nt, nx, ny, self.overlay):
                    # Move
                    c.x, c.y = nx, ny
                    moved = True
                    break

            # Reveal spawn leaf when first leaving original cell (force 80 regardless of prior value)
            if moved and not c.left_spawn_once:
                self.grid[oldy][oldx] = 80
                if (oldx, oldy) in self.overlay.cop_spawn_leaf:
                    self.overlay.cop_spawn_leaf.discard((oldx, oldy))
                c.left_spawn_once = True

            # Post-move collision with player
            if c.pos == player_pos:
                # No super, so player is hit
                ev.player_hit = True

        return ev

    # ---------- Helpers ----------
    def _in_bounds(self, x: int, y: int) -> bool:
        h = len(self.grid)
        w = len(self.grid[0]) if h else 0
        return 0 <= x < w and 0 <= y < h
