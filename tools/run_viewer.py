#!/usr/bin/env python3
# Minimal interactive viewer for Happyweed grids (no gameplay).
# - Sources: TSV goldens, our generator, or TheWinner2.py (if available)
# - HUD overlay (top-left digits) toggle: H
# - Optional bottom status bar (viewer-only) toggle: B
# - Source cycle (TSV ↔ OURS ↔ TW if present): G
# - 60 Hz fixed loop

import argparse, os
import pygame
from happyweed.render.tileset import Tileset

# ---------- TSV IO ----------
def read_tsv(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for ln in f:
            ln = ln.rstrip("\n")
            if ln:
                rows.append([int(x) for x in ln.split("\t")])
    if len(rows) != 12 or any(len(r) != 20 for r in rows):
        raise SystemExit(f"{path}: expected 12 rows of 20 columns.")
    return rows

# ---------- robust TheWinner2 loader ----------
_TW = None
def _load_twinner2():
    """Try importing TheWinner2; fall back to locating a file near repo root."""
    global _TW
    if _TW is not None:
        return _TW
    try:
        from importlib import import_module
        _TW = import_module("TheWinner2")
        return _TW
    except Exception:
        pass
    import importlib.util
    here = os.path.abspath(os.path.dirname(__file__))
    candidates = [
        os.path.normpath(os.path.join(os.getcwd(), "TheWinner2.py")),
        os.path.normpath(os.path.join(here, "..", "TheWinner2.py")),
        os.path.normpath(os.path.join(here, "..", "..", "TheWinner2.py")),
    ]
    for p in candidates:
        if os.path.exists(p):
            spec = importlib.util.spec_from_file_location("TheWinner2", p)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            _TW = mod
            return _TW
    _TW = None
    return None

# ---------- sources ----------
def grid_from_ours(level_set, level):
    from happyweed.mapgen.generator import generate_grid
    return generate_grid(level_set, level)

def grid_from_tw(level_set, level):
    TW = _load_twinner2()
    if TW is None:
        raise RuntimeError("TheWinner2.py not found; cannot use 'tw' source.")
    seed = TW.seed_from_set_level(level_set, level)
    return TW.generate_level(level_set, level, seed=seed)

def grid_from_tsv(level_set, level, indir):
    return read_tsv(os.path.join(indir, str(level_set), f"{level:02d}.tsv"))

# ---------- HUD overlay (top-left digits 0..9) ----------
def bake_level_digits_inplace(grid, level_idx: int):
    h = (level_idx // 100) % 10
    t = (level_idx // 10)  % 10
    o = level_idx % 10
    grid[0][0] = h
    grid[0][1] = t
    grid[0][2] = o

# ---------- status bar (viewer-only placeholder) ----------
def draw_status_bar(screen, y0, tile, get_tile_surface, *, time_ticks=0, score=0, lives=3, super_count=0):
    pygame.draw.rect(screen, (24, 24, 24), pygame.Rect(0, y0, 20*tile, tile))
    font = pygame.font.SysFont(None, max(10, tile // 2))
    def label(x, text):
        img = font.render(text, True, (220,220,220))
        screen.blit(img, (x, y0 + (tile - img.get_height()) // 2))
        return x + img.get_width() + (tile // 2)
    def digits(x, value, nd=3):
        s = f"{value:0{nd}d}"
        for ch in s:
            screen.blit(get_tile_surface(int(ch)), (x, y0)); x += tile
        return x
    x = tile // 2
    x = label(x, "TIME");  x = digits(x, time_ticks, 3); x += tile
    x = label(x, "SCORE"); x = digits(x, score, 6);     x += tile
    x = label(x, "LIVES"); x = digits(x, lives, 2);     x += tile
    x = label(x, "SUPER"); x = digits(x, super_count, 2)

# ---------- viewer ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", type=int, default=41, help="Level set number")
    ap.add_argument("--level", type=int, default=1, help="Level (1..25)")
    ap.add_argument("--tile", type=int, default=16, help="Tile size in pixels")
    ap.add_argument("--source", choices=["tsv", "ours", "tw"], default="tsv",
                    help="Where to load the grid from")
    ap.add_argument("--indir", type=str, default="data/golden_levels",
                    help="Directory containing TSVs when --source=tsv")
    ap.add_argument("--hud", action="store_true", help="Overlay HUD digits at top-left")
    ap.add_argument("--statusbar", action="store_true", help="Draw a bottom status bar (viewer-only)")
    args = ap.parse_args()

    pygame.init()
    pygame.display.set_caption("Happyweed Viewer")
    clock = pygame.time.Clock()

    # compute window size
    W, H = 20 * args.tile, 12 * args.tile
    status_h = args.tile if args.statusbar else 0
    screen = pygame.display.set_mode((W, H + status_h))

    # centralized tileset loader
    tiles = Tileset(args.tile)
    def get_tile_surface(tile_id: int) -> pygame.Surface:
        return tiles.view(tile_id, args.tile)

    level_set, level = args.set, args.level

    # Build available source cycle
    sources = ["tsv", "ours"]
    if _load_twinner2() is not None:
        sources.append("tw")
    source_mode = args.source
    if source_mode == "tw" and "tw" not in sources:
        source_mode = "ours"  # fallback if TW is missing

    def load_grid():
        if source_mode == "tsv":
            return grid_from_tsv(level_set, level, args.indir)
        elif source_mode == "ours":
            return grid_from_ours(level_set, level)
        else:
            try:
                return grid_from_tw(level_set, level)
            except Exception as e:
                print(f"[viewer] 'tw' unavailable: {e}")
                return grid_from_ours(level_set, level)

    grid = load_grid()
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
                elif ev.key == pygame.K_UP:
                    level_set += 1
                    grid = load_grid()
                elif ev.key == pygame.K_DOWN:
                    level_set = max(1, level_set - 1)
                    grid = load_grid()
                elif ev.key == pygame.K_g:
                    i = sources.index(source_mode)
                    source_mode = sources[(i + 1) % len(sources)]
                    grid = load_grid()
                elif ev.key == pygame.K_h:
                    args.hud = not args.hud
                elif ev.key == pygame.K_b:
                    args.statusbar = not args.statusbar
                    new_status_h = args.tile if args.statusbar else 0
                    if new_status_h != status_h:
                        status_h = new_status_h
                        screen = pygame.display.set_mode((W, H + status_h))

        # Prepare a copy if HUD is on (so we don't mutate the base grid)
        grid_to_draw = grid
        if args.hud:
            grid_to_draw = [row[:] for row in grid]
            bake_level_digits_inplace(grid_to_draw, level)

        # Draw
        screen.fill((0, 0, 0))
        for y in range(12):
            for x in range(20):
                screen.blit(get_tile_surface(grid_to_draw[y][x]), (x * args.tile, y * args.tile))

        if args.statusbar:
            draw_status_bar(
                screen, y0=12 * args.tile, tile=args.tile, get_tile_surface=get_tile_surface,
                time_ticks=0, score=0, lives=3, super_count=0
            )

        pygame.display.set_caption(
            f"Happyweed Viewer — Set {level_set}  Level {level}  [{source_mode.upper()}]  HUD:{args.hud}  BAR:{args.statusbar}"
        )
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()

if __name__ == "__main__":
    main()
