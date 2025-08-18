# tests/test_full_vs_tw.py
from importlib import import_module

from happyweed.rng import PMRandom
from happyweed.mapgen.carve import carve_leaf_grid
from happyweed.mapgen.placement import apply_all_placements
from happyweed.mapgen.jail import place_jail
from happyweed.tiles import wall_for_level

def mask_hud(grid, level_idx):
    # Overwrite [0][0..2] with current level wall tile to ignore HUD digits
    w = wall_for_level(level_idx)
    for i in (0,1,2):
        grid[0][i] = w

def build_ours(level_set, level_idx, seed):
    rng = PMRandom(seed & 0x7FFFFFFF)
    g = carve_leaf_grid(level_idx, rng, mode="steps", steps_cap=135)
    apply_all_placements(g, rng, level_idx)
    place_jail(g, rng, level_idx)
    mask_hud(g, level_idx)
    return g

def test_full_grid_matches_twinner2():
    TW = import_module("TheWinner2")
    # A spread across bands and fallbacks (+ one reuse case)
    cases = [(41,1), (41,5), (41,10), (41,15), (41,21), (41,25), (33,2)]
    for s, l in cases:
        seed = TW.seed_from_set_level(s, l)
        tw_grid = TW.generate_level(s, l, seed=seed)
        mask_hud(tw_grid, l)
        ours = build_ours(s, l, seed)
        assert ours == tw_grid, f"Mismatch at set {s} level {l}"
