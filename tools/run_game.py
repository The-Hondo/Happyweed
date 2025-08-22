# tools/run_game.py
# Runtime viewer for the engine Player + overlay tickers + minimal cop kills.
# - 60 Hz pygame loop
# - Buffered turning + configurable speed
# - Exit ticker (engine): premove 249→241 close; open 241→249 when leaves==0
# - Jail BR overlay (engine): flips 253→254 on first super kill; reverts after super
# - Score overlays 181..184 (engine) with lifetimes
# - Minimal cops: created from baked tiles, stationary; if player with super touches
#   them, they are sent to jail and score overlay appears (single-cop bug preserved).

from __future__ import annotations

import argparse
from typing import List, Tuple, Optional, Set

import pygame

# Project imports
try:
    from happyweed.mapgen.generator import generate_grid
    from happyweed.render.tileset import Tileset
    from happyweed.engine.player import Player
    from happyweed.engine.cop import Cop, jail_cells
    from happyweed.engine.collisions import (
        FLOOR_SUBSTRATE,
        build_runtime_overlay,
        premove_exit_flip,
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
    return positions  # 21..25 ambiguous; CLI can add


def find_cops(grid: List[List[int]]) -> List[Cop]:
    cops: List[Cop] = []
    for y, row in enumerate(grid):
        for x, t in enumerate(row):
            if t in (65, 66, 67):
                cops.append(Cop(x, y))
    return cops


# ---------- Main ----------

def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="Happyweed runtime (engine overlay tickers + cop kills)")
    parser.add_argument("--set", type=int, default=41, dest="level_set")
    parser.add_argument("--level", type=int, default=1)
    parser.add_argument("--tile", type=int, default=32, help="tile size in pixels")
    parser.add_argument("--fps", type=int, default=60)
    parser.add_argument("--step-ticks", type=int, default=8, help="ticks per tile movement (player speed)")
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

    # Cops from baked tiles + hidden-leaf accounting
    cops = find_cops(grid)
    overlay.cop_spawn_leaf = {c.pos for c in cops}

    # Leaves remaining = visible leaves (80) + hidden leaves under cop spawns
    leaves_remaining = sum(1 for row in grid for t in row if t == 80) + len(overlay.cop_spawn_leaf)

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

    running = True
    did_premove_flip = False
    total_points = 0

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
                elif event.key == pygame.K_k:
                    # Dev helper: simulate a single-cop super kill at player position
                    if player.super_active:
                        px, py = player.pos
                        total_points += on_super_kill_player(px, py, n_cops_on_tile=1, overlay=overlay)

        # --- One-tick game update ---
        if not did_premove_flip:
            premove_exit_flip(overlay)
            did_premove_flip = True

        # Engine-managed overlay tickers (exit, score overlays, jail BR)
        tick_overlay(
            overlay,
            leaves_remaining=leaves_remaining,
            super_active=player.super_active,
            grid=grid,
        )

        # Determine exit-open state from overlay
        exit_open = exit_is_open(overlay)

        ev = player.tick(exit_open=exit_open)
        if ev.leaf_collected:
            leaves_remaining = max(0, leaves_remaining - 1)

        # Super kill handling: if player is on any cop tile while super is active, send all cops
        # on that tile to jail and trigger score overlay. Points only for exactly 1 cop per tile.
        if player.super_active:
            px, py = player.pos
            same_tile = [c for c in cops if c.pos == (px, py)]
            if same_tile:
                n = len(same_tile)
                total_points += on_super_kill_player(px, py, n_cops_on_tile=n, overlay=overlay)
                # Choose jail slots in order TL, TR, BL, BR then wrap
                cells = jail_cells(overlay)
                for idx, cop in enumerate(same_tile):
                    cop.send_to_jail(overlay, slot_idx=(idx % max(1, len(cells))))

        # Release-from-jail mechanic after super ends (minimal: keep them in jail for now)
        # Future: add timers or exit pathing here.

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

        # Draw cops (stationary): jailed cops render inside jail; others at their positions
        jail_tiles = set(jail_cells(overlay))
        for cop in cops:
            cx, cy = cop.pos
            ctile = 65 if player.super_active else 66
            # If cop is in jail, force-draw at their jail coordinate
            if cop.in_jail:
                ctile = 65  # frozen look
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
        dbg = (
            f"set {args.level_set}-{args.level} pos=({px},{py}) dir={player.cur_dir} "
            f"exit={'OPEN' if exit_open else 'closed'} super={'ON' if player.super_active else 'off'} "
            f"spd={player.MOVE_PERIOD_TICKS}t/step leaves={leaves_remaining} pts={total_points}"
        )
        dbg_surf = font.render(dbg, True, (255, 255, 0))
        screen.blit(dbg_surf, (4, h * args.tile - 18))

        pygame.display.flip()
        clock.tick(args.fps)

    pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
