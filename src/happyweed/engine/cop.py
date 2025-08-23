# src/happyweed/engine/cop.py
# LST-style cop engine (direction priority + phasing) with a provisional roam/chase gate
# ----------------------------------------------------------------------------
# What is LST-accurate here
# - Cops may overlap tiles; no occupancy map. (Matches ROM behavior and scoring overlay rules.)
# - Passability for cops: treat 10..199 and 241..249 as passable; jail (>=250) passable for cops.
#   (We delegate to collisions.is_passable_runtime("cop", ...), which mirrors sub_74C6.)
# - Direction priority mirrors sub_7A1E intent / sub_7B54 commit:
#     1) Straight-ahead if it reduces |dx|+|dy| (bias to continue)
#     2) Primary axis toward player (|dx|>=|dy| → horizontal, else vertical)
#     3) Perpendicular toward-player, then its opposite
#     4) Reversal last (only when boxed in)
#   A tiny phase-based swap decorrelates ties to emulate the three-way pipeline (sub_8736).
# - Phased stepping: only cops whose `phase == manager_phase` step on this tick (natural separation).
# - Jail lifecycle: during super, kills park at BR (in_jail=True); on super falling-edge, release
#   all jailed cops in place and hold one period before movement resumes (visible release).
#
# What is provisional (to be tightened with exact constants from the LST)
# - Roam vs Chase gate: ROM calls a random-direction helper (sub_7986 → sub_56C2/_Random) under a
#   particular case inside 7A1E. The exact predicate is data-driven; until we lift those constants,
#   we approximate with a Manhattan distance gate (CHASE_RANGE = 6). Outside that radius cops 
#   pick a random legal step; within it they use the chase ordering above. This keeps visuals and
#   difficulty close to the ROM and will be swapped for the table-driven predicate when decoded.
# ----------------------------------------------------------------------------
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Tuple

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
    last_dir: XY = (0, 0)   # last committed step (dx,dy)
    phase: int = 0          # 0..2; which cohort this cop belongs to
    aggro: bool = False     # visual/logic hint: True when in chase mode

    def __post_init__(self) -> None:
        if self.spawn_x == 0 and self.spawn_y == 0:
            self.spawn_x, self.spawn_y = self.x, self.y
        self.phase %= 3

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
        self.last_dir = (0, 0)
        self.aggro = False

    def release_from_jail(self) -> None:
        self.in_jail = False
        self.last_dir = (0, 0)
        self.aggro = False

    def reset_to_spawn(self) -> None:
        self.x, self.y = self.spawn_x, self.spawn_y
        self.in_jail = False
        self.last_dir = (0, 0)
        # left_spawn_once stays latched
        self.aggro = False


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
    _super_prev: bool = False
    _phase_counter: int = 0  # 0..2
    CHASE_RANGE: int = 6     # → replace with LST-driven predicate

    # simple deterministic LCG for provisional roaming (ROM uses _Random)
    _rng_state: int = 0x13579BDF

    def __post_init__(self) -> None:
        for i, c in enumerate(self.cops):
            c.phase = i % 3
        # seed based on map footprint so runs are stable per level
        w = len(self.grid[0]) if self.grid else 20
        h = len(self.grid)
        self._rng_state ^= (w << 8) ^ (h << 4) ^ len(self.cops)

    # ---------- RNG (provisional) ----------
    def _rand(self, n: int) -> int:
        # LCG 32-bit, return 0..n-1
        self._rng_state = (1103515245 * self._rng_state + 12345) & 0xFFFFFFFF
        return (self._rng_state >> 16) % max(1, n)

    # ---------- Main tick ----------
    def tick(self, player_pos: XY, super_active: bool) -> CopTickEvents:
        ev = CopTickEvents()
        if not self.cops:
            return ev

        # Super falling-edge -> release jailed cops, then hold one period
        if self._super_prev and not super_active:
            for c in self.cops:
                if c.in_jail:
                    c.release_from_jail()
            self._cooldown = self.move_period_ticks
        self._super_prev = super_active

        # During super: freeze, but resolve kills at overlap
        if super_active:
            kills = [c for c in self.cops if (not c.in_jail) and c.pos == player_pos]
            if kills:
                n = len(kills)
                ev.points_awarded += on_super_kill_player(player_pos[0], player_pos[1], n_cops_on_tile=n, overlay=self.overlay)
                ev.kills_this_tick += n
                for c in kills:
                    c.send_to_jail(self.overlay, slot_idx=3)
            return ev

        # Move only on period boundaries
        if self._cooldown > 0:
            self._cooldown -= 1
            return ev
        self._cooldown = self.move_period_ticks

        # Phase gating
        self._phase_counter = (self._phase_counter + 1) % 3
        phase_now = self._phase_counter
        px, py = player_pos

        for c in self.cops:
            if c.in_jail or c.phase != phase_now:
                continue

            ox, oy = c.x, c.y

            # --- Roam vs Chase gate (provisional distance predicate) ---
            manh = abs(px - c.x) + abs(py - c.y)
            c.aggro = manh <= self.CHASE_RANGE

            # Candidate order
            if c.aggro:
                candidates = list(self._candidate_steps_chase(c, px, py))
            else:
                candidates = list(self._candidate_steps_roam(c))

            # Commit first passable candidate
            for nx, ny in candidates:
                if not self._in_bounds(nx, ny):
                    continue
                nt = self.grid[ny][nx]
                if is_passable_runtime("cop", nt, nx, ny, self.overlay):
                    c.x, c.y = nx, ny
                    c.last_dir = (nx - ox, ny - oy)
                    break

            # First leave -> reveal leaf at spawn
            if (c.x, c.y) != (ox, oy) and not c.left_spawn_once:
                self.grid[oy][ox] = 80
                self.overlay.cop_spawn_leaf.discard((ox, oy))
                c.left_spawn_once = True

            if c.pos == player_pos:
                ev.player_hit = True

        return ev

    def reset_on_player_death(self) -> None:
        for c in self.cops:
            c.reset_to_spawn()
        self._cooldown = self.move_period_ticks

    # ---------- Direction priority (LST-style chase) ----------
    def _candidate_steps_chase(self, c: Cop, px: int, py: int) -> Iterable[XY]:
        dx = 0 if c.x == px else (1 if px > c.x else -1)
        dy = 0 if c.y == py else (1 if py > c.y else -1)
        adx = abs(px - c.x)
        ady = abs(py - c.y)
        primary_h = adx >= ady

        ahead = (c.x + c.last_dir[0], c.y + c.last_dir[1]) if c.last_dir != (0, 0) else None
        def reduces(nx: int, ny: int) -> bool:
            return abs(px - nx) + abs(py - ny) < adx + ady

        order: List[XY] = []
        if ahead is not None and reduces(*ahead):
            order.append(ahead)

        # Primary axis toward-player
        if primary_h and dx != 0:
            order.append((c.x + dx, c.y))
        if (not primary_h) and dy != 0:
            order.append((c.x, c.y + dy))

        # Perpendiculars (toward then away)
        if dy != 0:
            order.append((c.x, c.y + dy))
            order.append((c.x, c.y - dy))
        if dx != 0:
            order.append((c.x + dx, c.y))
            order.append((c.x - dx, c.y))

        # Reversal last
        if c.last_dir != (0, 0):
            order.append((c.x - c.last_dir[0], c.y - c.last_dir[1]))

        # De-dup preserve order; small phase-based swap to decorrelate symmetric choices
        seen = set()
        prio: List[XY] = []
        for st in order:
            if st not in seen:
                prio.append(st)
                seen.add(st)
        if len(prio) >= 2 and (c.phase & 1):
            prio[0], prio[1] = prio[1], prio[0]
        return prio

    # ---------- Roaming (provisional; ROM uses sub_7986/_Random) ----------
    def _candidate_steps_roam(self, c: Cop) -> Iterable[XY]:
        # Prefer straight, then left/right, then reverse, but choose a random rotation.
        ahead = (c.x + c.last_dir[0], c.y + c.last_dir[1]) if c.last_dir != (0, 0) else (c.x, c.y)
        # 4-neighbors
        neighbors = [(c.x-1,c.y),(c.x+1,c.y),(c.x,c.y-1),(c.x,c.y+1)]
        k = self._rand(4)
        rot = neighbors[k:]+neighbors[:k]
        order: List[XY] = []
        if c.last_dir != (0,0):
            order.append(ahead)
        order.extend(rot)
        # Put reversal last
        if c.last_dir != (0, 0):
            order.append((c.x - c.last_dir[0], c.y - c.last_dir[1]))
        # de-dup
        seen=set(); uniq: List[XY]=[]
        for pt in order:
            if pt not in seen:
                uniq.append(pt); seen.add(pt)
        return uniq

    # ---------- Helpers ----------
    def _in_bounds(self, x: int, y: int) -> bool:
        h = len(self.grid)
        w = len(self.grid[0]) if h else 0
        return 0 <= x < w and 0 <= y < h
