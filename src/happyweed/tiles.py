# Canonical tile IDs (subset for generator)

LEAF = 80
PLAYER = 60
COP = 66
EXIT = 241
WALL_BASE = 200  # Levels 1..20 use 200+level; 21..25 → 255
JAIL_TL, JAIL_TR, JAIL_BL, JAIL_BR = 250, 251, 252, 253

def wall_for_level(level: int) -> int:
    return 255 if level >= 21 else (WALL_BASE + level)

def superdrug_for_level(level: int) -> int:
    # Levels 1–14: 80+level. Levels 15–25: 255.
    return 255 if level >= 15 else (LEAF + level)

def is_open(tile: int) -> bool:
    # Open classification per lst: strictly 10..199.
    return 10 <= tile <= 199
