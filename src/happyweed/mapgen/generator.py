# src/happyweed/mapgen/generator.py
# Exact wrapper around your proven generator.
from importlib import import_module

try:
    TW = import_module("TheWinner2")  # expects TheWinner2.py at repo root
except Exception as e:
    raise RuntimeError(
        "Could not import TheWinner2.py. Place it at the repo root."
    ) from e

def generate_grid(level_set: int, level: int):
    seed = TW.seed_from_set_level(level_set, level)
    grid = TW.generate_level(level_set, level, seed=seed)
    return grid  # already 20×12, headerless
