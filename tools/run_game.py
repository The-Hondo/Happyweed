#!/usr/bin/env python3
# Minimal fixed-60 Hz runtime scaffold:
# - draws our generated grid exactly
# - optional HUD digits (top-left inside the grid)
# - bottom status bar using ui/status_bar.py
# - keyboard: arrows = level nav, H = toggle HUD, B = toggle status bar, Esc = quit

import argparse
import pygame

from happyweed.mapgen.generator import generate_grid
from happyweed.render.tileset import Tileset
from happyweed.ui.status_bar import StatusBarState, render_status_bar

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

    def load_grid():
        return generate_grid(level_set, level)

    grid = load_grid()
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
                elif ev.key in (pygame.K_RIGHT, pygame.K_PAGEUP):
                    level = 1 if level == 25 else level + 1
                    grid = load_grid()
                elif ev.key in (pygame.K_LEFT, pygame.K_PAGEDOWN):
                    level = 25 if level == 1 else level - 1
                    grid = load_grid()
                elif ev.key == pygame.K_h:
                    hud_on = not hud_on
                elif ev.key == pygame.K_b:
                    bar_on = not bar_on
                    new_h = args.tile if bar_on else 0
                    if new_h != status_h:
                        status_h = new_h
                        screen = pygame.display.set_mode((W, H + status_h))

        # Placeholder time counter (real game will drive this later)
        status.time_ticks = (status.time_ticks + 1) % 1000

        # Prepare a copy if HUD overlay is enabled (don’t mutate base grid)
        draw_grid = grid
        if hud_on:
            draw_grid = [row[:] for row in grid]
            bake_level_digits_inplace(draw_grid, level)

        # Draw
        screen.fill((0, 0, 0))
        for y in range(12):
            for x in range(20):
                screen.blit(get_tile_surface(draw_grid[y][x]), (x * args.tile, y * args.tile))

        if bar_on:
            render_status_bar(screen, (0, 12 * args.tile), args.tile, get_tile_surface, state=status)

        pygame.display.set_caption(
            f"Happyweed Runtime — Set {level_set}  Level {level}  HUD:{hud_on}  BAR:{bar_on}"
        )
        pygame.display.flip()
        clock.tick(60)  # fixed 60 Hz

    pygame.quit()

if __name__ == "__main__":
    main()
