# src/happyweed/engine/cop.py
# Cop engine (movement + jail + death reset)
# v3 changes
# - LST-path *scaffold*: deterministic axis-first pursuit with no immediate reversal;
#   structured so we can swap in exact LST ordering once finalized without touching callers.
# - Jail lifecycle: cops sent to BR during super; on the *falling edge* of super, all jailed
#   cops are released in-place and resume movement (with a cooldown so the release is visible).
# - Death reset: returns cops to original spawns and holds their movement for one period so
#   the reset is visually obvious.

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple, Iterable

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
    last_dir: XY = (0, 0)  # last movement vector; used to avoid instant reversals

    def __post_init__(self):
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
        # Keep last_dir as-is; they will pick a legal move next tick

    def reset_to_spawn(self) -> None:
        self.x, self.y = self.spawn_x, self.spawn_y
        self.in_jail = False
        # Do NOT reset left_spawn_once; leaves remain as already revealed
        # Keep last_dir = (0,0) so first move isn't treated as reversal
        self.last_dir = (0, 0)


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
    _super_prev: bool = False  # track falling edge for jail release

    def tick(self, player_pos: XY, super_active: bool) -> CopTickEvents:
        ev = CopTickEvents()

        # Falling edge of super → release all jailed cops, then hold for a period
        if self._super_prev and not super_active:
            for c in self.cops:
                if c.in_jail:
                    c.release_from_jail()
            # Hold movement so the release state is visible before the first step
            self._cooldown = self.move_period_ticks

        self._super_prev = super_active

        # During super: freeze movement, but resolve overlap kills immediately
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

            # Candidate ordering (LST-path scaffold):
            for nx, ny in self._candidate_steps(c, px, py):
                if not self._in_bounds(nx, ny):
                    continue
                nt = self.grid[ny][nx]
                if is_passable_runtime("cop", nt, nx, ny, self.overlay):
                    c.x, c.y = nx, ny
                    c.last_dir = (nx - oldx, ny - oldy)
                    break

            # First leave → reveal a visible leaf (80) at the spawn
            if (c.x, c.y) != (oldx, oldy) and not c.left_spawn_once:
                self.grid[oldy][oldx] = 80
                self.overlay.cop_spawn_leaf.discard((oldx, oldy))
                c.left_spawn_once = True

            # Contact with player → report hit when no super
            if c.pos == player_pos:
                ev.player_hit = True

        return ev

    def reset_on_player_death(self) -> None:
        """Return all cops to their original spawns. Leaves remain as-is.
        Also pause their movement for one full period so the reset is visible.
        """
        for c in self.cops:
            c.reset_to_spawn()
        self._cooldown = self.move_period_ticks
        # Do NOT touch overlay.cop_spawn_leaf

    # ---------- Movement ordering (to be replaced with exact LST once decoded) ----------
    def _candidate_steps(self, c: Cop, px: int, py: int) -> Iterable[XY]:
        """Yield next-step candidates in priority order.
        Rule (scaffold):
        - Prefer the axis with larger |delta| toward the player.
        - Avoid immediate reversal unless there is no other legal option.
        - If primary axis blocked, try the two perpendiculars (toward the player first),
          then allow reversal as last resort.
        This is deterministic and easy to swap for the exact LST ordering later.
        """
        dx = 0 if c.x == px else (1 if px > c.x else -1)
        dy = 0 if c.y == py else (1 if py > c.y else -1)
        adx, ady = abs(px - c.x), abs(py - c.y)
        last = c.last_dir
        # helpers
        def is_rev(step: XY) -> bool:
            return (step[0] == -last[0] and step[1] == -last[1]) and (last != (0, 0))

        def push(step: XY, out: List[XY]):
            if not is_rev(step):
                out.append((c.x + step[0], c.y + step[1]))

        primary_h = adx >= ady
        candidates: List[XY] = []
        if primary_h and dx != 0:
            push((dx, 0), candidates)
            # then vertical toward player (dy first if any)
            if dy != 0:
                push((0, dy), candidates)
                push((0, -dy), candidates)
            # then horizontal opposite (only if not reversal; if both blocked we'll allow reversal later)
            push((-dx, 0), candidates)
        elif not primary_h and dy != 0:
            push((0, dy), candidates)
            if dx != 0:
                push((dx, 0), candidates)
                push((-dx, 0), candidates)
            push((0, -dy), candidates)
        # As a last resort, allow reversal
        rev = (-last[0], -last[1])
        if last != (0, 0):
            candidates.append((c.x + rev[0], c.y + rev[1]))
        # Ensure uniqueness and preserve order
        seen = set()
        ordered = []
        for cand in candidates:
            if cand not in seen:
                ordered.append(cand)
                seen.add(cand)
        return ordered

    # ---------- Helpers ----------
    def _in_bounds(self, x: int, y: int) -> bool:
        h = len(self.grid)
        w = len(self.grid[0]) if h else 0
        return 0 <= x < w and 0 <= y < h
