import os
from happyweed.mapgen.generator import generate_grid
from happyweed.tiles import wall_for_level

def read_tsv(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            rows.append([int(x) for x in line.split("\t")])
    return rows

def mask_hud(grid, level_idx):
    # Overwrite the top-left 3 cells (HUD digits) with the correct wall tile
    w = wall_for_level(level_idx)
    for i in (0,1,2):
        grid[0][i] = w

def test_set41_goldens_match():
    base = os.path.join("data", "golden_levels", "41")
    for lvl in range(1, 26):
        want = read_tsv(os.path.join(base, f"{lvl:02d}.tsv"))
        mask_hud(want, lvl)             # ignore HUD digits baked into TSVs
        got  = generate_grid(41, lvl)
        assert got == want, f"Mismatch at set 41 level {lvl}"
