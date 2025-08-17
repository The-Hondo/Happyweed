#!/usr/bin/env python3
# Minimal interactive viewer for Happyweed grids (no gameplay).
# - Loads tiles from assets/original/images[/tiles]/ {ID}.png or tile_{ID}.png
# - Displays a 20x12 grid at a chosen tile size
# - Page through levels/sets; toggle source between TSV and TheWinner2

import os, argparse
import pygame

ASSET_DIR = os.path.join("assets", "original", "images")

def find_tile_path(tile_id):
    candidates = [
        os.path.join(ASSET_DIR, "tiles", f"{tile_id}.png"),
        os.path.join(ASSET_DIR, "tiles", f"tile_{tile_id}.png"),
        os.path.join(ASSET_DIR, f"{tile_id}.png"),
        os.path.join(ASSET_DIR, f"tile_{tile_id}.png"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None

def fallback_color(tile_id):
    if tile_id >= 250: return (200,200,255)
    if tile_id >= 241: return (255,220,0)
    if tile_id >= 200: return (80,80,80)
    if tile_id >= 100: return (160,255,160)
    if tile_id >= 80:  return (0,220,0)
    return (220,220,220)

def read_tsv(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for ln in f:
            ln = ln.rstrip("\n")
            if ln:
                rows.append([int(x) for x in ln.split("\t")])
    if len(rows) != 12 or any(len(r) != 20 for r in rows):
        raise SystemExit(f"{path}: expected 12 rows of 20 columns")
    return rows

def grid_from_tw(level_set, level):
    from importlib import import_module
    TW = import_module("TheWinner2")
    seed = TW.seed_from_set_level(level_set, level)
    return TW.generate_level(level_set, level, seed=seed)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", type=int, default=41)
    ap.add_argument("--level", type=int, default=1)
    ap.add_argument("--tile", type=int, default=16)
    ap.add_argument("--source", choices=["tsv", "tw"], default="tsv",
                    help="tsv: read from data/golden_levels; tw: generate via TheWinner2.py")
    ap.add_argument("--indir", type=str, default="data/golden_levels")
    args = ap.parse_args()

    pygame.init()
    pygame.display.set_caption("Happyweed Viewer")
    W, H = 20*args.tile, 12*args.tile
    screen = pygame.display.set_mode((W, H))
    font = pygame.font.SysFont(None, max(10, args.tile // 2))

    # Tile cache: id -> surface
    cache = {}
    def get_tile_surface(tile_id):
        if tile_id in cache: return cache[tile_id]
        path = find_tile_path(tile_id)
        if path and os.path.exists(path):
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
    source_mode = args.source  # "tsv" or "tw"

    def load_grid():
        if source_mode == "tsv":
            tsv = os.path.join(args.indir, str(level_set), f"{level:02d}.tsv")
            return read_tsv(tsv)
        return grid_from_tw(level_set, level)

    running = True
    grid = load_grid()
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
                elif ev.key == pygame.K_UP:
                    level_set += 1
                    grid = load_grid()
                elif ev.key == pygame.K_DOWN:
                    level_set = max(1, level_set - 1)
                    grid = load_grid()
                elif ev.key == pygame.K_g:  # toggle source
                    source_mode = "tw" if source_mode == "tsv" else "tsv"
                    grid = load_grid()
        # draw
        screen.fill((0,0,0))
        for y in range(12):
            for x in range(20):
                screen.blit(get_tile_surface(grid[y][x]), (x*args.tile, y*args.tile))
        pygame.display.set_caption(f"Happyweed Viewer — Set {level_set}  Level {level}  [{source_mode.upper()}]")
        pygame.display.flip()
        pygame.time.wait(16)  # ~60 Hz

    pygame.quit()

if __name__ == "__main__":
    main()
