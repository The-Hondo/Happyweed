from dataclasses import dataclass
from typing import Callable

@dataclass
class StatusBarState:
    time_ticks: int = 0    # viewer/runtime-facing counter; unit is up to the caller
    score: int = 0
    lives: int = 3
    super_count: int = 0

def render_status_bar(
    screen, origin_xy: tuple[int,int], tile: int,
    get_tile_surface: Callable[[int], "pygame.Surface"],
    state: StatusBarState
) -> None:
    """
    Draw a 1-tile-high status bar using tile digits 0..9 if available,
    else a simple text fallback. Does not mutate the grid.
    """
    import pygame  # local import to avoid hard dep when not used
    ox, oy = origin_xy
    w = 20 * tile
    pygame.draw.rect(screen, (24, 24, 24), pygame.Rect(ox, oy, w, tile))
    font = pygame.font.SysFont(None, max(10, tile // 2))

    def label(x, text):
        img = font.render(text, True, (220,220,220))
        screen.blit(img, (ox + x, oy + (tile - img.get_height()) // 2))
        return x + img.get_width() + (tile // 2)

    def digits(x, value, nd=3):
        s = f"{value:0{nd}d}"
        for ch in s:
            d = int(ch)
            screen.blit(get_tile_surface(d), (ox + x, oy)); x += tile
        return x

    x = tile // 2
    x = label(x, "TIME");  x = digits(x, state.time_ticks % 1000, 3); x += tile
    x = label(x, "SCORE"); x = digits(x, state.score % 1_000_000, 6); x += tile
    x = label(x, "LIVES"); x = digits(x, max(0, min(99, state.lives)), 2); x += tile
    x = label(x, "SUPER"); x = digits(x, max(0, min(99, state.super_count)), 2)
