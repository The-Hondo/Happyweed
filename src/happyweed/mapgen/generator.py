# src/happyweed/mapgen/generator.py
# Exact wrapper around your proven generator, with robust import for CI.

import os, sys, importlib.util

def _load_twinner2():
    # First try a normal import (works locally when CWD is repo root)
    try:
        return __import__("TheWinner2")
    except ModuleNotFoundError:
        pass

    # Fallbacks: look relative to this file and the repo root (CI-safe)
    here = os.path.abspath(os.path.dirname(__file__))
    candidates = [
        os.path.normpath(os.path.join(here, "../../../TheWinner2.py")),  # repo root relative to src/happyweed/mapgen
        os.path.normpath(os.path.join(os.getcwd(), "TheWinner2.py")),   # current working dir
    ]
    for p in candidates:
        if os.path.exists(p):
            spec = importlib.util.spec_from_file_location("TheWinner2", p)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod

    # Last resort: helpful error
    raise RuntimeError(
        "Could not locate TheWinner2.py. Place it at the repo root (same level as src/, data/, tools/)."
    )

TW = _load_twinner2()

def generate_grid(level_set: int, level: int):
    seed = TW.seed_from_set_level(level_set, level)
    return TW.generate_level(level_set, level, seed=seed)
