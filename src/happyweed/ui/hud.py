# src/happyweed/ui/hud.py
from typing import List, Tuple

def level_digits(level_idx: int) -> Tuple[int, int, int]:
    """
    Encode the level number as 3 tiles (hundreds, tens, ones), exactly like
    the original HUD: zero-padded, digits are tile IDs 0..9.
    """
    if not (0 <= level_idx <= 999):
        raise ValueError("level_idx must be 0..999")
    h = (level_idx // 100) % 10
    t = (level_idx // 10)  % 10
    o = level_idx % 10
    return h, t, o

def bake_level_digits(grid20x12: List[List[int]], level_idx: int) -> None:
    """
    Overwrite the top-left three cells with the HUD digits.
    Mutates the grid in place (matches how the original wrote the HUD into the tilemap).
    """
    h, t, o = level_digits(level_idx)
    grid20x12[0][0] = h
    grid20x12[0][1] = t
    grid20x12[0][2] = o
