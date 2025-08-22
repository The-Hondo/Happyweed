# src/happyweed/engine/collisions.py
# Engine-side collisions + runtime overlay/tickers (no pygame).
# - Classifier (port of sub_74C6): open 10..199, exit 241..249, jail >=250 for cops only
# - Passability helpers for player/cop
# - Enter-effects for player (leaf/super -> 180, exit touch)
# - Super-kill scoring overlay (181..184) with single-cop scoring bug
# - Exit animation ticker (premove flip to 249 → close to 241; open when leaves==0)
# - Jail BR toggle (253→254 on first super kill during a super window; revert after)

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Set, Tuple, List

XY = Tuple[int, int]

# Constants
FLOOR_SUBSTRATE = 180  # confirmed by LST write-back #$B4
JAIL_BR_NORMAL = 253
JAIL_BR_TICKED = 254

# Tunables (to be calibrated exactly against video later)
EXIT_TICKS_PER_FRAME = 10   # frames between 241<->249 steps
SCORE_OVERLAY_TICKS = 24    # how long 181..184 stays visible (~0.4s @60Hz)


@dataclass
class RuntimeOverlay:
    # Super disambiguation (esp. for level >= 15 where 255 can be super OR wall)
    super_positions: Set[XY] = field(default_factory=set)

    # Exit state
    exit_pos: Optional[XY] = None
    exit_frame: int = 241  # 241..249
    exit_dir: int = 0      # -1 closing, +1 opening, 0 hold
    exit_timer: int = 0

    # Scoring overlays: (x,y) -> {'tile': 181..184, 'timer': ticks}
    score_fx: Dict[XY, Dict[str, int]] = field(default_factory=dict)

    # Jail bottom-right cell state (253 or 254)
    jail_br_pos: Optional[XY] = None
    jail_br_state: int = JAIL_BR_NORMAL

    # Hidden leaf under cop spawns (revealed/collected on first visit)
    cop_spawn_leaf: Set[XY] = field(default_factory=set)


# ---------- Classifier and passability ----------

def classify_tile(tile: int, modeB: bool) -> int:
    """Port of sub_74C6: return class code; callers treat <2 as blocked.
      - 10..199 -> 3 (open)
      - 241..249 -> 2 (exit frames, passable)
      - >=250 -> 3 only if modeB (jail pass-through for cops), else blocked
    """
    if 10 <= tile <= 199:
        return 3
    if 241 <= tile <= 249:
        return 2
    if modeB and tile >= 250:
        return 3
    return 1


def is_passable_runtime(actor: str, tile: int, x: int, y: int, overlay: RuntimeOverlay) -> bool:
    """Shared passability for player/cop with super exception for the player."""
    if (x, y) in overlay.super_positions:
        return True  # allow stepping onto a super (incl. 255) to collect it
    modeB = (actor == "cop")
    return classify_tile(tile, modeB) >= 2


# ---------- Enter effects ----------

def on_enter_player(tile: int, x: int, y: int, level: int, overlay: RuntimeOverlay, grid: List[List[int]]) -> Dict[str, bool]:
    """Called after the player steps into (x,y). Mutates grid/overlay and returns flags."""
    events = {"leaf_collected": False, "super_collected": False, "exit_touched": False}

    # Hidden leaf under cop spawn: collect immediately on entry
    if (x, y) in overlay.cop_spawn_leaf:
        grid[y][x] = FLOOR_SUBSTRATE
        overlay.cop_spawn_leaf.discard((x, y))
        events["leaf_collected"] = True
        return events

    # Leaf
    if tile == 80:
        grid[y][x] = FLOOR_SUBSTRATE
        events["leaf_collected"] = True
        return events

    # Super (80+level on early levels OR overlay-marked coord for 255 on later levels)
    if tile == 80 + level or (x, y) in overlay.super_positions:
        grid[y][x] = FLOOR_SUBSTRATE
        overlay.super_positions.discard((x, y))
        events["super_collected"] = True
        return events

    # Exit touch event (always walkable); caller decides if open -> end level
    if 241 <= tile <= 249:
        events["exit_touched"] = True

    return events


def on_enter_cop(tile: int, x: int, y: int, overlay: RuntimeOverlay, grid: List[List[int]]) -> None:
    # Cops overlay only; no consumption of tiles at runtime
    return None


# ---------- Super kill & scoring overlay ----------

def on_super_kill_player(x: int, y: int, n_cops_on_tile: int, overlay: RuntimeOverlay) -> int:
    """Trigger score overlay at (x,y) during an active super.
    Visual: tile = 181..184 based on count (min-capped at 4). Held for SCORE_OVERLAY_TICKS.
    Scoring bug: award points only if exactly one cop was on the tile.
    Returns awarded points (500 if single cop, else 0).
    """
    frame = min(max(n_cops_on_tile, 1), 4)  # 1..4
    overlay.score_fx[(x, y)] = {"tile": 180 + frame, "timer": SCORE_OVERLAY_TICKS}

    # Flip jail BR on the first kill in the current super window
    if overlay.jail_br_pos is not None:
        overlay.jail_br_state = JAIL_BR_TICKED

    return 500 if n_cops_on_tile == 1 else 0


# ---------- Overlay lifecycle (exit, score fx, jail BR) ----------

def build_runtime_overlay(grid: List[List[int]], *, super_positions: Optional[Set[XY]] = None) -> RuntimeOverlay:
    """Construct overlay from a grid: finds exit/jail BR; callers may pass super_positions."""
    exit_pos: Optional[XY] = None
    jail_br: Optional[XY] = None
    for y, row in enumerate(grid):
        for x, t in enumerate(row):
            if exit_pos is None and 241 <= t <= 249:
                exit_pos = (x, y)
            if t == JAIL_BR_NORMAL:
                jail_br = (x, y)
    return RuntimeOverlay(
        super_positions=set(super_positions or set()),
        exit_pos=exit_pos,
        exit_frame=grid[exit_pos[1]][exit_pos[0]] if exit_pos else 241,
        exit_dir=0,
        exit_timer=0,
        jail_br_pos=jail_br,
        jail_br_state=JAIL_BR_NORMAL,
    )


def premove_exit_flip(overlay: RuntimeOverlay) -> None:
    """Call once at level start before first player input: set exit to 249 and begin closing."""
    if overlay.exit_pos is None:
        return
    overlay.exit_frame = 249
    overlay.exit_dir = -1
    overlay.exit_timer = EXIT_TICKS_PER_FRAME


def tick_overlay(overlay: RuntimeOverlay, *, leaves_remaining: int, super_active: bool, grid: Optional[List[List[int]]] = None) -> None:
    """Advance overlay state one tick (exit animation, score overlays, jail BR reversion)."""
    # Exit open/close state machine
    if overlay.exit_pos is not None:
        # Open when all leaves collected
        if leaves_remaining == 0:
            overlay.exit_dir = +1
        # Step frames when timer elapses
        if overlay.exit_dir != 0:
            if overlay.exit_timer > 0:
                overlay.exit_timer -= 1
            if overlay.exit_timer == 0:
                overlay.exit_timer = EXIT_TICKS_PER_FRAME
                overlay.exit_frame = max(241, min(249, overlay.exit_frame + overlay.exit_dir))
                if overlay.exit_frame in (241, 249):
                    overlay.exit_dir = 0

    # Score overlays lifetime; ensure map reverts to 180 at end as belt-and-suspenders
    if overlay.score_fx:
        for (x, y), data in list(overlay.score_fx.items()):
            data["timer"] = max(0, data.get("timer", 0) - 1)
            if data["timer"] == 0:
                overlay.score_fx.pop((x, y), None)
                if grid is not None:
                    try:
                        grid[y][x] = FLOOR_SUBSTRATE
                    except Exception:
                        pass

    # Jail BR reverts when super is no longer active
    if overlay.jail_br_pos is not None and overlay.jail_br_state == JAIL_BR_TICKED and not super_active:
        overlay.jail_br_state = JAIL_BR_NORMAL


# Convenience: is the exit considered open this tick?

def exit_is_open(overlay: RuntimeOverlay) -> bool:
    return overlay.exit_frame == 249
