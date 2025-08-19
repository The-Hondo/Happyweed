# tests/test_hud_digits.py
import os
from copy import deepcopy

from happyweed.mapgen.generator import generate_grid
from happyweed.ui.hud import bake_level_digits

def read_tsv(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if line:
                rows.append([int(x) for x in line.split("\t")])
    return rows

def test_hud_overlay_matches_tsv_goldens():
    # Pick a few—covers 1, a two-digit, and 25
    for lvl in (1, 10, 25):
        want = read_tsv(os.path.join("data", "golden_levels", "41", f"{lvl:02d}.tsv"))
        got = generate_grid(41, lvl)
        bake_level_digits(got, lvl)  # add HUD like the original
        assert got == want, f"HUD mismatch when overlaying at level {lvl}"
