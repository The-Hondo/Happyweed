# tools/run_game.py
# Slim pygame runner using engine.state.GameState (modular). Keeps rendering/input here,
# and all gameplay orchestration in the engine.

from __future__ import annotations

import argparse
from typing import Optional

import pygame

try:
    from happyweed.engine.state import GameState
    from happyweed.render.tileset import Tileset
    from happyweed.engine.collisions import FLOOR_SUBSTRATE
except Exception as e:  # pragma: no cover
    print("[run_game] Failed to import project modules:", e)
    print("Ensure you installed the package in editable mode: pip install -e .")
    raise


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="Happyweed runtime (modular)")
    parser.add_argument("--set", type=int, default=41, dest="level_set")
    parser.add_argument("--level", type=int, default=1)
    parser.add_argument("--tile", type=int, default=32)
    parser.add_argument("--fps", type=int, default=60)
    parser.add_argument("--step-ticks", type=int, default=8)
    parser.add_argument("--cop-ticks", type=int, default=10)
    parser.add_argument("--spawn", type=str, default=None, help="x,y override")
    parser.add_argument("--supers", type=str, default=None, help="semicolon list of x,y for L>=21")
    args = parser.parse_args(argv)

    # Build engine state
    spawn_xy = None
    if args.spawn:
        try:
            sx, sy = map(int, args.spawn.split(","))
            spawn_xy = (sx, sy)
        except Exception:
            print("Invalid --spawn; expected x,y. Ignoring.")
            spawn_xy = None

    super_overrides = set()
    if args.supers:
        for chunk in args.supers.split(";"):
            if not chunk:
                continue
            try:
                x, y = map(int, chunk.split(","))
                super_overrides.add((x, y))
            except Exception:
                print(f"Invalid --supers entry: {chunk}")

    state = GameState(
        level_set=args.level_set,
        level=args.level,
        player_step_ticks=args.step_ticks,
        cop_step_ticks=args.cop_ticks,
        spawn_override=spawn_xy,
        super_overrides=super_overrides or None,
    )

    # Pygame init
    if not pygame.get_init():
        pygame.init()
    if not pygame.font.get_init():
        pygame.font.init()

    # FIX: Tileset requires tile_size positional arg in your repo
    try:
        tileset = Tileset(args.tile)
    except TypeError:
        # Back-compat for alternate signature
        tileset = Tileset(tile_size=args.tile)

    tile_px = args.tile
    screen = pygame.display.set_mode((len(state.grid[0]) * tile_px, len(state.grid) * tile_px))
    pygame.display.set_caption(f"Happyweed — set {args.level_set} level {args.level}")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Consolas", 16)

    def blit_tile(tile_id: int, x: int, y: int) -> None:
        surf = tileset.get(tile_id)
        if surf is None:
            rect = pygame.Rect(x * tile_px, y * tile_px, tile_px, tile_px)
            pygame.draw.rect(screen, (24, 24, 24), rect)
            txt = font.render(str(tile_id), True, (200, 200, 200))
            screen.blit(txt, (rect.x + 2, rect.y + 2))
        else:
            if surf.get_width() != tile_px or surf.get_height() != tile_px:
                surf = pygame.transform.scale(surf, (tile_px, tile_px))
            screen.blit(surf, (x * tile_px, y * tile_px))

    running = True

    while running:
        # Input → engine intents
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key in (pygame.K_UP, pygame.K_w):
                    state.player.set_wanted_dir("up")
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    state.player.set_wanted_dir("down")
                elif event.key in (pygame.K_LEFT, pygame.K_a):
                    state.player.set_wanted_dir("left")
                elif event.key in (pygame.K_RIGHT, pygame.K_d):
                    state.player.set_wanted_dir("right")
                elif event.key == pygame.K_SPACE:
                    state.player.activate_super()
                elif event.key in (pygame.K_LEFTBRACKET, pygame.K_COMMA):
                    state.player.set_move_period(state.player.MOVE_PERIOD_TICKS + 1)
                elif event.key in (pygame.K_RIGHTBRACKET, pygame.K_PERIOD):
                    state.player.set_move_period(max(1, state.player.MOVE_PERIOD_TICKS - 1))

        # Tick engine once
        _out = state.tick()

        # Draw
        screen.fill((0, 0, 0))
        for y, row in enumerate(state.grid):
            for x, t in enumerate(row):
                t_draw = FLOOR_SUBSTRATE if t in (60, 61, 62, 63, 65, 66, 67) else t
                # Exit frame substitution
                if state.overlay.exit_pos == (x, y):
                    t_draw = state.overlay.exit_frame
                blit_tile(t_draw, x, y)

        # Score overlays
        for (ox, oy), data in list(state.overlay.score_fx.items()):
            blit_tile(data.get("tile", 181), ox, oy)

        # Jail BR = 254 while super kill window active
        if state.overlay.jail_br_pos and state.overlay.jail_br_state == 254:
            jx, jy = state.overlay.jail_br_pos
            blit_tile(254, jx, jy)

        # Draw cops (hide while jailed during super)
        for cop in state.cops:
            if cop.in_jail and state.player.super_active:
                continue
            cx, cy = cop.pos
            blit_tile(65 if state.player.super_active else 66, cx, cy)

        # Draw player
        px, py = state.player.pos
        blit_tile(state.player.sprite_tile(), px, py)

        # Debug HUD
        leaves_remaining = sum(1 for row in state.grid for t in row if t == 80) + len(state.overlay.cop_spawn_leaf)
        dbg = (
            f"set {args.level_set}-{args.level} pos=({px},{py}) dir={state.player.cur_dir} "
            f"exit={'OPEN' if _out.exit_open else 'closed'} super={'ON' if state.player.super_active else 'off'} "
            f"spd={state.player.MOVE_PERIOD_TICKS}/{state.copman.move_period_ticks} leaves={leaves_remaining}"
        )
        screen.blit(font.render(dbg, True, (255, 255, 0)), (4, len(state.grid) * tile_px - 18))

        pygame.display.flip()
        clock.tick(args.fps)

    pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
