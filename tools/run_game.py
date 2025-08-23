# tools/run_game.py
# Runtime viewer for Player + overlay tickers + CopManager movement/collisions.
# v11 fixes:
# - Cop reset on death preserves each cop's left_spawn_once and never rewrites a leaf.
#   We ALWAYS reset existing Cop objects back to (spawn_x,spawn_y) and clear in_jail.
#   No reconstruction of cop list (which used to lose left_spawn_once and replant 80 later).
# - Exit cadence wired to LST behavior via engine constant EXIT_TICKS_PER_FRAME=1.
#   Closing happens once at level start; opening once when leaves==0. On death, exit snaps to 241 and holds.

from __future__ import annotations

import argparse
from typing import List, Tuple, Optional, Set

import pygame

# Project imports
try:
    from happyweed.mapgen.generator import generate_grid
    from happyweed.render.tileset import Tileset
    from happyweed.engine.player import Player
    from happyweed.engine.cop import Cop, CopManager, jail_cells
    from happyweed.engine.collisions import (
        FLOOR_SUBSTRATE,
        build_runtime_overlay,
        tick_overlay,
        exit_is_open,
        on_super_kill_player,
    )
except Exception as e:  # pragma: no cover
    print("[run_game] Failed to import project modules:", e)
    print("Ensure you installed the package in editable mode: pip install -e .")
    raise

XY = Tuple[int, int]

# ---------- Helpers ----------

def in_bounds(grid: List[List[int]], x: int, y: int) -> bool:
    h = len(grid)
    w = len(grid[0]) if h else 0
    return 0 <= x < w and 0 <= y < h


def find_player_spawn_by_tile(grid: List[List[int]]) -> Optional[XY]:
    for y, row in enumerate(grid):
        for x, t in enumerate(row):
            if t in (60, 61, 62, 63):
                return (x, y)
    return None


def infer_spawn(grid: List[List[int]]) -> XY:
    cx, cy = 10, 6
    if in_bounds(grid, cx, cy) and 10 <= grid[cy][cx] <= 199:
        return (cx, cy)
    for r in range(1, 20):
        for dx in range(-r, r + 1):
            for dy in (-r, r):
                x, y = cx + dx, cy + dy
                if in_bounds(grid, x, y) and 10 <= grid[y][x] <= 199:
                    return (x, y)
        for dy in range(-r + 1, r):
            for dx in (-r, r):
                x, y = cx + dx, cy + dy
                if in_bounds(grid, x, y) and 10 <= grid[y][x] <= 199:
                    return (x, y)
    return (0, 0)


def super_tile_id_for_level(level: int) -> int:
    return 80 + level if level <= 14 else 255


def infer_supers(grid: List[List[int]], level: int) -> Set[XY]:
    positions: Set[XY] = set()
    if level <= 14:
        target = super_tile_id_for_level(level)
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


def find_cops(grid: List[List[int]]) -> List[Cop]:
    cops: List[Cop] = []
    for y, row in enumerate(grid):
        for x, t in enumerate(row):
            if t in (65, 66, 67):
                cops.append(Cop(x, y))
    return cops


def count_leaves(grid: List[List[int]], overlay) -> int:
    visible = sum(1 for row in grid for t in row if t == 80)
    hidden = len(overlay.cop_spawn_leaf)
    return visible + hidden


# ---------- Main ----------

def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="Happyweed runtime (CopManager)")
    parser.add_argument("--set", type=int, default=41, dest="level_set")
    parser.add_argument("--level", type=int, default=1)
    parser.add_argument("--tile", type=int, default=32, help="tile size in pixels")
    parser.add_argument("--fps", type=int, default=60)
    parser.add_argument("--step-ticks", type=int, default=8, help="ticks per tile movement (player speed)")
    parser.add_argument("--cop-ticks", type=int, default=10, help="ticks per cop movement (lower=faster)")
    parser.add_argument("--spawn", type=str, default=None, help="spawn as x,y (overrides inference)")
    parser.add_argument("--supers", type=str, default=None, help="semicolon-separated list of x,y for super positions (for L>=21)")
    parser.add_argument("--force-exit-frame", type=int, default=None, help="force exit frame 241..249 for rendering")
    args = parser.parse_args(argv)

    # Generate grid
    grid = generate_grid(args.level_set, args.level)
    h = len(grid)
    w = len(grid[0]) if h else 0

    # Initialize pygame early (Tileset may use font)
    if not pygame.get_init():
        pygame.init()
    if not pygame.font.get_init():
        pygame.font.init()

    # Tileset with robust init + scaling wrapper
    base_tileset = None
    for _args, _kwargs in [
        ((), {}),
        ((args.tile,), {}),
        ((), {"tile_px": args.tile}),
        ((), {"tile_size": args.tile}),
    ]:
        try:
            base_tileset = Tileset(*_args, **_kwargs)
            break
        except TypeError:
            base_tileset = None
    if base_tileset is None:
        base_tileset = Tileset()

    class _ScaledTileset:
        def __init__(self, base, tile_px: int):
            self.base = base
            self.tile_px = tile_px
            self._cache = {}
        def get(self, tile_id: int):
            surf = self.base.get(tile_id)
            if surf is None:
                return None
            key = (tile_id, self.tile_px)
            if key in self._cache:
                return self._cache[key]
            if surf.get_width() == self.tile_px and surf.get_height() == self.tile_px:
                self._cache[key] = surf
                return surf
            scaled = pygame.transform.scale(surf, (self.tile_px, self.tile_px))
            self._cache[key] = scaled
            return scaled

    tileset = _ScaledTileset(base_tileset, args.tile)

    # Overlay (engine manages exit/jail/score tickers)
    overlay = build_runtime_overlay(grid, super_positions=infer_supers(grid, args.level))

    # Manual supers for 21..25 (ambiguous 255 walls)
    if args.supers:
        for chunk in args.supers.split(";"):
            if not chunk:
                continue
            try:
                sx, sy = map(int, chunk.split(","))
                overlay.super_positions.add((sx, sy))
            except Exception:
                print(f"Invalid --supers entry: {chunk} (expected x,y)")

    # Cops from baked tiles + manager
    cops = find_cops(grid)
    overlay.cop_spawn_leaf = {c.pos for c in cops}
    copman = CopManager(grid=grid, overlay=overlay, cops=cops, move_period_ticks=max(1, args.cop_ticks))

    # Spawn
    map_spawn = find_player_spawn_by_tile(grid)
    if args.spawn:
        try:
            sx, sy = map(int, args.spawn.split(","))
            spawn_xy = (sx, sy)
        except Exception:
            print("Invalid --spawn; expected x,y. Falling back to map/inference.")
            spawn_xy = map_spawn or infer_spawn(grid)
    else:
        spawn_xy = map_spawn or infer_spawn(grid)

    player = Player(grid=grid, overlay=overlay, level_index=args.level, spawn_xy=spawn_xy)
    player.set_move_period(args.step_ticks)

    # Pygame window
    screen = pygame.display.set_mode((w * args.tile, h * args.tile))
    pygame.display.set_caption(f"Happyweed runtime — set {args.level_set} level {args.level}")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Consolas", 16)

    # ---- Exit lifecycle flags ----
    exit_close_armed = True  # only at actual level start

    def arm_exit_for_level_start():
        nonlocal exit_close_armed
        if overlay.exit_pos is not None:
            overlay.exit_frame = 249
            overlay.exit_dir = 0
            overlay.exit_timer = 1  # engine uses step-per-loop; set to 1 so first step happens next tick
        exit_close_armed = True

    def force_exit_closed_hold():
        if overlay.exit_pos is not None:
            overlay.exit_frame = 241
            overlay.exit_dir = 0
            overlay.exit_timer = 1

    def handle_player_death():
        # Respawn player
        player.force_respawn()
        # Exit should be CLOSED and static after death (no re-closing animation)
        force_exit_closed_hold()
        # Reset cops to original spawns WITHOUT recreating objects → preserve left_spawn_once
        if hasattr(copman, "reset_on_player_death"):
            try:
                copman.reset_on_player_death()
            except Exception:
                for c in copman.cops:
                    if hasattr(c, "spawn_x"):
                        c.x, c.y = c.spawn_x, c.spawn_y
                        c.in_jail = False
        else:
            for c in copman.cops:
                if hasattr(c, "spawn_x"):
                    c.x, c.y = c.spawn_x, c.spawn_y
                    c.in_jail = False

    # Pre-state at level start: show 249 then close once after the level begins
    arm_exit_for_level_start()

    running = True

    def draw_map_layer():
        for y in range(h):
            for x in range(w):
                t = grid[y][x]
                if t in (60, 61, 62, 63, 65, 66, 67):
                    t_draw = FLOOR_SUBSTRATE
                else:
                    t_draw = t
                if overlay.exit_pos == (x, y):
                    tile_id = args.force_exit_frame if args.force_exit_frame is not None else overlay.exit_frame
                else:
                    tile_id = t_draw
                surf = tileset.get(tile_id)
                if surf is None:
                    rect = pygame.Rect(x * args.tile, y * args.tile, args.tile, args.tile)
                    pygame.draw.rect(screen, (24, 24, 24), rect)
                    txt = font.render(str(tile_id), True, (200, 200, 200))
                    screen.blit(txt, (rect.x + 2, rect.y + 2))
                else:
                    screen.blit(surf, (x * args.tile, y * args.tile))

    # ---------- Main loop ----------
    while running:
        # --- Input ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key in (pygame.K_UP, pygame.K_w):
                    player.set_wanted_dir("up")
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    player.set_wanted_dir("down")
                elif event.key in (pygame.K_LEFT, pygame.K_a):
                    player.set_wanted_dir("left")
                elif event.key in (pygame.K_RIGHT, pygame.K_d):
                    player.set_wanted_dir("right")
                elif event.key == pygame.K_SPACE:
                    player.activate_super()
                elif event.key in (pygame.K_LEFTBRACKET, pygame.K_COMMA):
                    player.set_move_period(player.MOVE_PERIOD_TICKS + 1)
                elif event.key in (pygame.K_RIGHTBRACKET, pygame.K_PERIOD):
                    player.set_move_period(max(1, player.MOVE_PERIOD_TICKS - 1))

        # --- Cops step FIRST ---
        cev = copman.tick(player_pos=player.pos, super_active=player.super_active)
        if cev.player_hit and not player.super_active:
            handle_player_death()
            # Draw a frame immediately to show closed exit (241) after death
            screen.fill((0, 0, 0))
            draw_map_layer()
            pygame.display.flip()
            clock.tick(args.fps)
            continue

        # --- Exit open state for this tick (before player move) ---
        exit_open = exit_is_open(overlay)

        # --- Player step ---
        ev = player.tick(exit_open=exit_open)

        # One-time closing: begin once the actual level begins (you moved at least once)
        if exit_close_armed and not player.pre_move_phase:
            if overlay.exit_pos is not None:
                overlay.exit_dir = -1
                if overlay.exit_timer <= 0:
                    overlay.exit_timer = 1
            exit_close_armed = False

        # --- Overlap collisions AFTER player move ---
        if not player.super_active:
            if any((not c.in_jail) and c.pos == player.pos for c in copman.cops):
                handle_player_death()
                screen.fill((0, 0, 0))
                draw_map_layer()
                pygame.display.flip()
                clock.tick(args.fps)
                continue
        else:
            overlapping = [c for c in copman.cops if (not c.in_jail) and c.pos == player.pos]
            if overlapping:
                n = len(overlapping)
                _ = on_super_kill_player(player.pos[0], player.pos[1], n_cops_on_tile=n, overlay=overlay)
                cells = jail_cells(overlay)
                br = cells[-1] if cells else None
                for c in overlapping:
                    c.send_to_jail(overlay, slot_idx=3)
                    if br:
                        c.x, c.y = br

        # --- Tick overlay timers at the END to reflect any resets/armings above ---
        tick_overlay(overlay, leaves_remaining=count_leaves(grid, overlay), super_active=player.super_active, grid=grid)

        # --- Rendering ---
        screen.fill((0, 0, 0))
        draw_map_layer()

        # Score overlays (181..184)
        for (ox, oy), data in list(overlay.score_fx.items()):
            tile_id = data.get("tile", 181)
            surf = tileset.get(tile_id)
            if surf is not None:
                screen.blit(surf, (ox * args.tile, oy * args.tile))

        # Jail BR = 254 during super-kill window
        if overlay.jail_br_pos and overlay.jail_br_state == 254:
            jx, jy = overlay.jail_br_pos
            jsurf = tileset.get(254)
            if jsurf is not None:
                screen.blit(jsurf, (jx * args.tile, jy * args.tile))

        # Draw cops (moving): hide jailed cops during super; otherwise draw at their positions
        for cop in copman.cops:
            if cop.in_jail and player.super_active:
                continue
            cx, cy = cop.pos
            ctile = 65 if player.super_active else 66
            csurf = tileset.get(ctile)
            if csurf is not None:
                screen.blit(csurf, (cx * args.tile, cy * args.tile))

        # Draw player sprite on top
        px, py = player.pos
        player_tile = player.sprite_tile()
        psurf = tileset.get(player_tile)
        if psurf is None:
            rect = pygame.Rect(px * args.tile, py * args.tile, args.tile, args.tile)
            pygame.draw.rect(screen, (80, 200, 120), rect, 2)
        else:
            screen.blit(psurf, (px * args.tile, py * args.tile))

        # HUD: tiny debug
        leaves_remaining_dbg = count_leaves(grid, overlay)
        dbg = (
            f"set {args.level_set}-{args.level} pos=({px},{py}) dir={player.cur_dir} "
            f"exit={'OPEN' if exit_is_open(overlay) else 'closed'} super={'ON' if player.super_active else 'off'} "
            f"spd={player.MOVE_PERIOD_TICKS}/{copman.move_period_ticks} leaves={leaves_remaining_dbg}"
        )
        dbg_surf = font.render(dbg, True, (255, 255, 0))
        screen.blit(dbg_surf, (4, h * args.tile - 18))

        pygame.display.flip()
        clock.tick(args.fps)

    pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
