#!/usr/bin/env python3
# Minimal fixed-60 Hz runtime scaffold:
# - draws our generated grid exactly
# - optional HUD digits (top-left inside the grid)
# - bottom status bar using ui/status_bar.py
# - keyboard: arrows = level nav, H = toggle HUD, B = toggle status bar, Esc = quit

import os, argparse, pygame

ASSET_DIR = os.path.join("assets", "original", "images")
TILES_DIR = os.path.join(ASSET_DIR, "tiles")

def _exists(p): return os.path.exists(p)

def find_tile_path(tile_id: int):
    for p in (
        os.path.join(TILES_DIR, f"{tile_id}.png"),
        os.path.join(TILES_DIR, f"tile_{tile_id}.png"),
        os.path.join(ASSET_DIR, f"{tile_id}.png"),
        os.path.join(ASSET_DIR, f"tile_{tile_id}.png"),
    ):
        if _exists(p): return p
    return None

def bake_level_digits_inplace(grid, level_idx: int):
    h = (level_idx // 100) % 10
    t = (level_idx // 10)  % 10
    o = level_idx % 10
    grid[0][0] = h; grid[0][1] = t; grid[0][2] = o

def main():
    from happyweed.mapgen.generator import generate_grid
    from happyweed.ui.status_bar import StatusBarState, render_status_bar

    ap = argparse.ArgumentParser()
    ap.add_argument("--set", type=int, default=41)
    ap.add_argument("--level", type=int, default=1)
    ap.add_argument("--tile", type=int, default=16)
    ap.add_argument("--hud", action="store_true")
    ap.add_argument("--statusbar", action="store_true")
    args = ap.parse_args()

    pygame.init()
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, max(10, args.tile // 2))

    W, H = 20 * args.tile, 12 * args.tile
    status_h = args.tile if args.statusbar else 0
    screen = pygame.display.set_mode((W, H + status_h))
    pygame.display.set_caption("Happyweed Runtime")

    # Tile cache
    cache = {}
    def fallback_color(tile_id):
        if tile_id >= 250: return (200,200,255,255)
        if tile_id >= 241: return (255,220,0,255)
        if tile_id >= 200: return (80,80,80,255)
        if tile_id >= 100: return (160,255,160,255)
        if tile_id >= 80:  return (0,220,0,255)
        return (220,220,220,255)

    def get_tile_surface(tile_id: int) -> pygame.Surface:
        if tile_id in cache: return cache[tile_id]
        path = find_tile_path(tile_id)
        if path and _exists(path):
            img = pygame.image.load(path).convert_alpha()
            if img.get_size() != (args.tile, args.tile):
                img = pygame.transform.scale(img, (args.tile, args.tile))
        else:
            img = pygame.Surface((args.tile, args.tile), pygame.SRCALPHA)
            img.fill(fallback_color(tile_id))
            txt = font.render(str(tile_id), True, (0,0,0))
            r = txt.get_rect(center=(args.tile//2, args.tile//2))
            img.blit(txt, r)
        cache[tile_id] = img
        return img

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

        # Update simple counters (viewer/runtime placeholder—real game will drive these)
        status.time_ticks = (status.time_ticks + 1) % 1000

        # Prepare a draw copy if HUD is on
        draw_grid = grid
        if hud_on:
            draw_grid = [row[:] for row in grid]
            bake_level_digits_inplace(draw_grid, level)

        # Draw
        screen.fill((0,0,0))
        for y in range(12):
            for x in range(20):
                screen.blit(get_tile_surface(draw_grid[y][x]), (x*args.tile, y*args.tile))

        if bar_on:
            render_status_bar(screen, (0, 12*args.tile), args.tile, get_tile_surface, state=status)

        pygame.display.set_caption(f"Happyweed Runtime — Set {level_set}  Level {level}  HUD:{hud_on}  BAR:{bar_on}")
        pygame.display.flip()
        clock.tick(60)  # fixed 60 Hz

    pygame.quit()

if __name__ == "__main__":
    main()
