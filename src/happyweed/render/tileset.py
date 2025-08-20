# src/happyweed/render/tileset.py
from __future__ import annotations
import os
import pygame
from functools import lru_cache
from typing import Tuple

ASSET_DIR = os.path.join("assets", "original", "images")
TILES_DIR = os.path.join(ASSET_DIR, "tiles")

def _path_candidates(tile_id: int) -> Tuple[str, ...]:
    return (
        os.path.join(TILES_DIR, f"{tile_id}.png"),
        os.path.join(TILES_DIR, f"tile_{tile_id}.png"),
        os.path.join(ASSET_DIR, f"{tile_id}.png"),
        os.path.join(ASSET_DIR, f"tile_{tile_id}.png"),
    )

def _fallback_color(tile_id: int) -> Tuple[int, int, int, int]:
    if tile_id >= 250: return (200, 200, 255, 255)   # jail
    if tile_id >= 241: return (255, 220,   0, 255)   # exit
    if tile_id >= 200: return ( 80,  80,  80, 255)   # walls (incl 255)
    if tile_id >= 100: return (160, 255, 160, 255)
    if tile_id >=  80: return (  0, 220,   0, 255)   # leaves/super
    return (220, 220, 220, 255)

class Tileset:
    """
    Tiny cached loader:
      - Accepts 255.png or tile_255.png
      - Looks in assets/original/images/tiles/ and assets/original/images/
      - Returns pygame.Surface of exactly (tile_size, tile_size)
    """
    def __init__(self, tile_size: int, font=None):
        self.tile_size = tile_size
        self.font = font or pygame.font.SysFont(None, max(10, tile_size // 2))

    @lru_cache(maxsize=512)
    def get(self, tile_id: int) -> pygame.Surface:
        # load once at default size; scale on demand in view()
        for p in _path_candidates(tile_id):
            if os.path.exists(p):
                img = pygame.image.load(p).convert_alpha()
                return img
        # fallback: colored tile with ID text
        img = pygame.Surface((self.tile_size, self.tile_size), pygame.SRCALPHA)
        img.fill(_fallback_color(tile_id))
        txt = self.font.render(str(tile_id), True, (0, 0, 0))
        r = txt.get_rect(center=(self.tile_size // 2, self.tile_size // 2))
        img.blit(txt, r)
        return img

    @lru_cache(maxsize=2048)
    def view(self, tile_id: int, size: int) -> pygame.Surface:
        base = self.get(tile_id)
        if base.get_size() == (size, size):
            return base
        return pygame.transform.scale(base, (size, size))
