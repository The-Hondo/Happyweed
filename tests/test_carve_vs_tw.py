# tests/test_carve_vs_tw.py
import os
from importlib import import_module

from happyweed.rng import PMRandom
from happyweed.mapgen.carve import carve_leaf_grid

# Helper: return set of (x,y) (0-based screen coords) where tile == 80
def leaf_coords(grid20x12):
    out = set()
    for y in range(12):
        for x in range(20):
            if grid20x12[y][x] == 80:
                out.add((x, y))
    return out

def run_case(level_set, level):
    TW = import_module("TheWinner2")
    seed = TW.seed_from_set_level(level_set, level)
    tw_grid = TW.generate_level(level_set, level, seed=seed)  # full grid w/ placements

    rng = PMRandom(seed & 0x7FFFFFFF)
    ours = carve_leaf_grid(level, rng, mode="steps", steps_cap=135)

    assert leaf_coords(ours) == leaf_coords(tw_grid), f"Leaf trail mismatch for set {level_set} level {level}"

def test_carve_matches_tw_various_levels():
    # A spread across the difficulty bands and wall/super fallbacks
    for (s, l) in [
        (41, 1),   # early
        (41, 5),   # mid band (2 super)
        (41, 10),  # single super
        (41, 15),  # super=255 fallback
        (41, 21),  # wall=255 fallback
        (41, 25),  # end
        (33, 2),   # known level reuse case (E-collisions)
    ]:
        run_case(s, l)
