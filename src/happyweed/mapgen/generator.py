# src/happyweed/mapgen/generator.py
# Canonical level generator using our reimplementation (no TheWinner2 dependency).

from ..rng import PMRandom, seed_from_set_level
from ..tiles import wall_for_level
from .carve import carve_leaf_grid
from .placement import apply_all_placements
from .jail import place_jail


def generate_grid(level_set: int, level: int):
    seed = seed_from_set_level(level_set, level)   # ← use closed-form
    rng = PMRandom(seed & 0x7FFFFFFF)

    grid = carve_leaf_grid(level, rng, mode="steps", steps_cap=135)
    apply_all_placements(grid, rng, level)
    place_jail(grid, rng, level)
    return grid