# src/happyweed/engine/collisions.py
# Engine-side collisions + runtime overlay/tickers (no pygame).
# v4 changes
# - EXIT_TICKS_PER_FRAME = 1 (exact): derived from LST open/close loop which updates the
#   exit frame (subq/addq #1) on each pass without an intermediate delay counter.
#   Evidence (snover_Happyweed.lst):
#     • Init 249 (open):
#         ROM:00007C04  move.w  #$F9,-(sp)
#         ROM:00007C1A  move.w  #$F9,-$1D10(a0,d0.w*2)
#     • Closing branch ($22==0):
#         ROM:00007ED4  cmpi.w  #$F1,-$1D10(a0,d0.w*2)
#         ROM:00007EEC  subq.w  #1,-$1D10(a0,d0.w*2)
#     • Opening branch ($22==1):
#         ROM:00007E80  cmpi.w  #$F9,-$1D10(a0,d0.w*2)
#         ROM:00007E98  addq.w  #1,-$1D10(a0,d0.w*2)
#   Both paths immediately draw the new frame via sub_6ADE; no countdown is present in this
#   routine, so we step one frame per game loop tick.

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Set, Tuple, List

XY = Tuple[int, int]

# Constants
FLOOR_SUBSTRATE = 180
JAIL_BR_NORMAL = 253
JAIL_BR_TICKED = 254

# Timers (runner ticks ~60 Hz)
EXIT_TICKS_PER_FRAME = 1  # exact per-LST: step every loop
SCORE_OVERLAY_TICKS = 80  # from LST: move.w #$50 to FX timer


@dataclass
class RuntimeOverlay:
    super_positions: Set[XY] = field(default_factory=set)

    # Exit state
    exit_pos: Optional[XY] = None
    exit_frame: int = 241  # 241..249
    exit_dir: int = 0      # -1 closing, +1 opening, 0 hold
    exit_timer: int = 0

    # Scoring overlays
    score_fx: Dict[XY, Dict[str, int]] = field(default_factory=dict)

    # Jail bottom-right cell state
    jail_br_pos: Optional[XY] = None
    jail_br_state: int = JAIL_BR_NORMAL

    # Hidden leaf under cop spawns
    cop_spawn_leaf: Set[XY] = field(default_factory=set)


# ---------- Classifier and passability ----------

def classify_tile(tile: int, modeB: bool) -> int:
    if 10 <= tile <= 199:
        return 3
    if 241 <= tile <= 249:
        return 2
    if modeB and tile >= 250:
        return 3
    return 1


def is_passable_runtime(actor: str, tile: int, x: int, y: int, overlay: RuntimeOverlay) -> bool:
    if (x, y) in overlay.super_positions:
        return True  # allow stepping onto a super (incl. 255) to collect it
    modeB = (actor == "cop")
    return classify_tile(tile, modeB) >= 2


# ---------- Enter effects ----------

def on_enter_player(tile: int, x: int, y: int, level: int, overlay: RuntimeOverlay, grid: List[List[int]]) -> Dict[str, bool]:
    events = {"leaf_collected": False, "super_collected": False, "exit_touched": False}

    if (x, y) in overlay.cop_spawn_leaf:
        grid[y][x] = FLOOR_SUBSTRATE
        overlay.cop_spawn_leaf.discard((x, y))
        events["leaf_collected"] = True
        return events

    if tile == 80:
        grid[y][x] = FLOOR_SUBSTRATE
        events["leaf_collected"] = True
        return events

    if tile == 80 + level or (x, y) in overlay.super_positions:
        grid[y][x] = FLOOR_SUBSTRATE
        overlay.super_positions.discard((x, y))
        events["super_collected"] = True
        return events

    if 241 <= tile <= 249:
        events["exit_touched"] = True

    return events


def on_enter_cop(tile: int, x: int, y: int, overlay: RuntimeOverlay, grid: List[List[int]]) -> None:
    return None


# ---------- Super kill & scoring overlay ----------

def on_super_kill_player(x: int, y: int, n_cops_on_tile: int, overlay: RuntimeOverlay) -> int:
    frame = min(max(n_cops_on_tile, 1), 4)  # 1..4
    overlay.score_fx[(x, y)] = {"tile": 180 + frame, "timer": SCORE_OVERLAY_TICKS}
    if overlay.jail_br_pos is not None:
        overlay.jail_br_state = JAIL_BR_TICKED
    return 500 if n_cops_on_tile == 1 else 0


# ---------- Overlay lifecycle ----------

def build_runtime_overlay(grid: List[List[int]], *, super_positions: Optional[Set[XY]] = None) -> RuntimeOverlay:
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


def tick_overlay(overlay: RuntimeOverlay, *, leaves_remaining: int, super_active: bool, grid: Optional[List[List[int]]] = None) -> None:
    # Opening when all leaves collected
    if overlay.exit_pos is not None and leaves_remaining == 0 and overlay.exit_frame < 249:
        overlay.exit_dir = +1

    # Step frames per LST (one per loop)
    if overlay.exit_pos is not None and overlay.exit_dir != 0:
        if overlay.exit_timer > 0:
            overlay.exit_timer -= 1
        if overlay.exit_timer == 0:
            overlay.exit_timer = EXIT_TICKS_PER_FRAME
            overlay.exit_frame = max(241, min(249, overlay.exit_frame + overlay.exit_dir))
            if overlay.exit_frame in (241, 249):
                overlay.exit_dir = 0

    # Score overlays lifetime; revert to floor on expiry (belt-and-suspenders)
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

    # Jail BR reversion when super ends
    if overlay.jail_br_pos is not None and overlay.jail_br_state == JAIL_BR_TICKED and not super_active:
        overlay.jail_br_state = JAIL_BR_NORMAL


def exit_is_open(overlay: RuntimeOverlay) -> bool:
    return overlay.exit_frame == 249
