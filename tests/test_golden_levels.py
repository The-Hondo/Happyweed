# tests/test_golden_levels.py
import os

from happyweed.mapgen.generator import generate_grid

def read_tsv(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            rows.append([int(x) for x in line.split("\t")])
    return rows

def test_set41_goldens_match():
    base = os.path.join("data", "golden_levels", "41")
    for lvl in range(1, 26):
        want = read_tsv(os.path.join(base, f"{lvl:02d}.tsv"))
        got  = generate_grid(41, lvl)
        assert got == want, f"Mismatch at set 41 level {lvl}"
