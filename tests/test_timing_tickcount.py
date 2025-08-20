# tests/test_timing_tickcount.py
from importlib import import_module
from happyweed.timing import s16, tick_over, make_linear_provider
from happyweed.rng import PMRandom
from happyweed.mapgen.carve import carve_leaf_grid

def leaf_coords(grid):
    return {(x, y) for y in range(12) for x in range(20) if grid[y][x] == 80}

def test_s16_and_tick_over_rollover():
    # Signed-16 interpretation
    assert s16(0x7FFF) == 32767
    assert s16(0x8000) == -32768
    assert s16(0xFFFF) == -1

    # cur > start + 3 using signed semantics (no rollover)
    assert tick_over(1000, 1004, 3) is True
    assert tick_over(1000, 1003, 3) is False

    # Rollover: start near 0xFFFF, cur wraps to small numbers
    start = 0xFFFE
    assert tick_over(start, 0x0002, 3) is True   # +4 across wrap
    assert tick_over(start, 0x0001, 3) is False  # +3 across wrap

def test_carve_tick_mode_matches_twinner2():
    TW = import_module("TheWinner2")
    # Use a linear provider (1 tick per carve iteration) so the carve stops after >3 ticks
    tp = make_linear_provider(start=12345)

    cases = [(41, 1), (41, 10), (41, 21)]
    for s, l in cases:
        seed = TW.seed_from_set_level(s, l)

        # TW reference grid in tick mode (very short trail due to early timeout)
        tw_grid = TW.generate_level(s, l, seed=seed, mode="tick", tick_provider=tp)

        # Our carve in tick mode with the same provider
        rng = PMRandom(seed & 0x7FFFFFFF)
        ours = carve_leaf_grid(l, rng, mode="tick", steps_cap=135, tick_provider=tp)

        assert leaf_coords(ours) == leaf_coords(tw_grid), f"Tick-mode carve mismatch at set {s} level {l}"
