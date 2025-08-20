#!/usr/bin/env python3
# Minimal fixed-60 Hz runtime scaffold + player movement:
# - draws our generated grid exactly
# - finds PLAYER start from the grid placement
# - replaces start cell with OPEN floor (tile 10) so movement rules are correct
# - tick-based player steps with strict "open = 10..199" rule
# - HUD digits toggle (H) + placeholder status bar (B)
# - Arrows = set desired direction; PageUp/PageDown = change level; Esc = quit

import argparse
import pygame

from happyweed.mapgen.generator import generate_grid
from happyweed.render.tileset import Tileset
from happyweed.ui.status_bar import StatusBarState, render_status_bar
from happyweed.tiles import PLAYER  # and your asset defines; floor/open is tile 10 by convention

from happyweed.engine.player import (
    PlayerState, DIR_LEFT, DIR_RIGHT, DIR_UP, DIR_DOWN,
    set_desired, update_player, find_player_start
)

OPEN_FLOOR = 10  # canonical "open" tile (strict open range is 10..199)

def bake_level_digits_inplace(grid, level_idx: int):
    """Write zero-padded 3 digits into [0][0..2]; matches original in-grid HUD."""
    h = (level_idx // 100) % 10
    t = (level_idx // 10)  % 10
    o = level_idx % 10
    grid[0][0] = h; grid[0][1] = t; grid[0][2] = o

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", type=int, default=41)
    ap.add_argument("--level", type=int, default=1)
    ap.add_argument("--tile", type=int, default=16)
    ap.add_argument("--hud", action="store_true")
    ap.add_argument("--statusbar", action="store_true")
    args = ap.parse_args()

    pygame.init()
    clock = pygame.time.Clock()

    # Window size (optionally one extra tile row for the status bar)
    W, H = 20 * args.tile, 12 * args.tile
    status_h = args.tile if args.statusbar else 0
    screen = pygame.display.set_mode((W, H + status_h))
    pygame.display.set_caption("Happyweed Runtime")

    # Centralized tileset loader
    tiles = Tileset(args.tile)
    def get_tile_surface(tile_id: int) -> pygame.Surface:
        return tiles.view(tile_id, args.tile)

    level_set, level = args.set, args.level

    def load_grid_and_spawn():
        """Generate grid, locate player start, and restore that cell to OPEN_FLOOR (10)."""
        g = generate_grid(level_set, level)
        sx, sy = find_player_start(g, PLAYER)
        if (sx, sy) == (-1, -1):
            # Fallback: if no PLAYER tile (shouldn't happen), park at first open cell
            for yy in range(12):
                for xx in range(20):
                    if 10 <= g[yy][xx] <= 199:
                        sx, sy = xx, yy
                        break
                if sx != -1:
                    break
        # Replace the PLAYER tile in the grid with open floor so movement rules operate correctly
        g[sy][sx] = OPEN_FLOOR
        return g, PlayerState(x=sx, y=sy, dir=None, desired=None)

    grid, player = load_grid_and_spawn()
    hud_on = args.hud
    bar_on = args.statusbar
    status = StatusBarState(time_ticks=0, score=0, lives=3, super_count=0)

    running = True
    while running:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    running = False

                # Level navigation: use PageUp/PageDown ONLY (leave arrows for movement)
                elif ev.key == pygame.K_PAGEUP:
                    level = 1 if level == 25 else level + 1
                    grid, player = load_grid_and_spawn()
                elif ev.key == pygame.K_PAGEDOWN:
                    level = 25 if level == 1 else level - 1
                    grid, player = load_grid_and_spawn()

                # UI toggles
                elif ev.key == pygame.K_h:
                    hud_on = not hud_on
                elif ev.key == pygame.K_b:
                    bar_on = not bar_on
                    new_h = args.tile if bar_on else 0
                    if new_h != status_h:
                        status_h = new_h
                        screen = pygame.display.set_mode((W, H + status_h))

                # Steering: buffer a desired direction (Pac-man style)
                elif ev.key == pygame.K_LEFT:
                    set_desired(player, DIR_LEFT)
                elif ev.key == pygame.K_RIGHT:
                    set_desired(player, DIR_RIGHT)
                elif ev.key == pygame.K_UP:
                    set_desired(player, DIR_UP)
                elif ev.key == pygame.K_DOWN:
                    set_desired(player, DIR_DOWN)

        # Placeholder time counter (real game will drive this later)
        status.time_ticks = (status.time_ticks + 1) % 1000

        # Advance player by one tick (one tile at most)
        update_player(grid, player)

        # Prepare draw copy if HUD overlay is enabled (don’t mutate base grid)
        draw_grid = grid
        if hud_on:
            draw_grid = [row[:] for row in grid]
            bake_level_digits_inplace(draw_grid, level)

        # Draw map
        screen.fill((0, 0, 0))
        for y in range(12):
            for x in range(20):
                screen.blit(get_tile_surface(draw_grid[y][x]), (x * args.tile, y * args.tile))

        # Draw player sprite (uses the PLAYER tile image on top of the map)
        screen.blit(get_tile_surface(PLAYER), (player.x * args.tile, player.y * args.tile))

        if bar_on:
            render_status_bar(screen, (0, 12 * args.tile), args.tile, get_tile_surface, state=status)

        pygame.display.set_caption(
            f"Happyweed Runtime — Set {level_set}  Level {level}  HUD:{hud_on}  BAR:{bar_on}  Pos:({player.x},{player.y})"
        )
        pygame.display.flip()
        clock.tick(60)  # fixed 60 Hz

    pygame.quit()

if __name__ == "__main__":
    main()
